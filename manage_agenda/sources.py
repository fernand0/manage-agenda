import datetime
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dateparser
from socialModules import moduleHtml
from socialModules.moduleContent import display_posts
from socialModules.moduleRules import moduleRules
from socialModules.configMod import CONFIGDIR, select_from_list

from manage_agenda.base import write_file
from manage_agenda.config import config
from manage_agenda.connections import select_api
from manage_agenda.extraction import _process_event_with_llm_and_calendar
from manage_agenda.llm import select_llm
from manage_agenda.web import reduce_html


@dataclass
class Args:
    """Arguments container for CLI commands."""

    interactive: bool = False
    delete: Optional[bool] = None
    source: Optional[str] = None
    ai: Optional[str] = None
    verbose: bool = False
    destination: Optional[str] = None
    text: Optional[str] = None
    output: str = "calendar"
    force_refresh: bool = False


def get_add_sources(rules=None):
    """Returns a list of available sources for the add command."""
    rules = rules or moduleRules.from_config()
    email_sources = rules.selectRule(["gmail", "imap"])
    return email_sources, [("web/http", "set", "(Enter URLs or leave empty)")] + [
        ("text", "set", "(enter filenames or leave empty)")
    ]


def print_first_10_lines(content, content_type="content"):
    """Prints the first 10 lines of the given content."""
    print(f"\n--- First 10 lines of {content_type} ---")
    for i, line in enumerate(content.splitlines()):
        if i >= 10:
            break
        print(line)
    print("-------------------------------------\n")


def _get_msgs_from_folder(args, source_name, rules=None):
    """Helper function to get posts stored in some folder."""
    # FIXME: maybe a folder argument?

    if source_name and isinstance(source_name, list):
        txt_files = source_name
    else:
        target_dir = Path(config.MSG_TXT_DIR)
        txt_files = target_dir.glob("*.txt")

    posts = []
    for file_path in txt_files:
        file_path = Path(file_path)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            file_name = file_path.stem
            posts.append([file_name, content])

    if not posts:
        if not os.path.exists(target_dir):
            print(f"There is no {target_dir} directory")
        else:
            print(f"There are no posts in {target_dir}")
        posts = None

    return None, posts

def _get_events_from_calendar(args, api_src, calendar=None):
    """Helper function to get events from a specific calendar."""
    "FIXME: maybe a folder argument?"

    if calendar:
        api_src.setCalendar(calendar)
    api_src.setPosts()
    posts = api_src.getPosts()

    return(posts)


def _get_emails_from_folder(args, api_src, folder=None):
    """Helper function to get emails from a specific folder."""
    "FIXME: maybe a folder argument?"

    posts = None

    if not folder:
        folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    if not label:
        print(f"There are no posts tagged with label {folder}")
    else:
        api_src.setChannel(folder)
        api_src.setPosts()
        posts = api_src.getPosts()

    return posts


def list_folder(args, service):
    """List posts from the selected folder for a supported service."""
    rules = moduleRules.from_config()
    if service in ["email", "imap", "gmail"]:
        api_src = rules.selectRuleInteractive(service=service, title="Select mail account")
        posts = _get_emails_from_folder(args, api_src)
    elif service == "gcalendar":
        api_src = rules.selectRuleInteractive(service=service, title="Select calendar account")
        posts = _get_events_from_calendar(args, api_src)
    else:
        raise ValueError(f"Unsupported folder service: {service}")
    display_posts(api_src, posts)














def _get_post_datetime_and_diff(post_date):
    """
    Calculates the post datetime and the difference in days from now.

    Args:
        post_date (str or datetime.datetime): The date of the post.

    Returns:
        tuple: A tuple containing the post datetime and the time difference in days.
    """
    if isinstance(post_date, datetime.datetime):
        post_date_time = post_date
    elif post_date.isdigit():
        post_date_time = datetime.datetime.fromtimestamp(int(post_date) / 1000)
    else:
        from email.utils import parsedate_to_datetime

        try:
            post_date_time = parsedate_to_datetime(post_date)
        except (ValueError, TypeError):
            parsed = dateparser.parse(post_date)
            if parsed is not None:
                post_date_time = parsed
            else:
                try:
                    parts = [int(p) for p in post_date.split("-") if p.isdigit()]
                    post_date_time = datetime.datetime(parts[0], parts[1], parts[2])
                except (IndexError, ValueError):
                    post_date_time = datetime.datetime.now()

    try:
        import pytz

        # Define the timezone
        madrid_tz = pytz.timezone("Europe/Madrid")

        # Make post_date_time timezone-aware if it's naive
        if post_date_time.tzinfo is None:
            post_date_time = madrid_tz.localize(post_date_time)

        # Get the current time as timezone-aware
        now_aware = datetime.datetime.now(madrid_tz)

        time_difference = now_aware - post_date_time
        logging.debug(f"Date: {post_date_time} Diff: {time_difference.days}")
    except Exception as e:
        logging.error(f"Error processing post date: {e}")
        time_difference = datetime.timedelta(0)

    return post_date_time, time_difference


def _delete_email(args, api_src, post_id, source_name, rules=None):
    """Deletes an email, handling interactive confirmation and connection errors."""
    delete_confirmed = False
    if args.interactive:
        confirmation = input("Do you want to remove the label from the email? (y/n): ")
        if confirmation.lower() == "y":
            delete_confirmed = True
    elif args.delete:  # Only auto-confirm if not interactive but delete flag is set
        delete_confirmed = True

    if delete_confirmed:
        max_retries = 1
        label = None
        for attempt in range(max_retries + 1):
            try:
                print(f"Service: {api_src.service.lower()}")
                res = ""
                if "imap" not in api_src.service.lower():
                    print(f"label: {api_src.getChannel()}")
                    logging.info(f"label: {api_src.getChannel()}")
                    folder = api_src.getChannel()
                    label = api_src.getLabels(folder)
                    logging.info(f"label: {label}")
                    res = api_src.modifyLabels(post_id, label[0], None)
                    logging.info(f"Label removed from email {post_id}.")
                else:
                    label = api_src.getChannel()
                    api_src.getClient().select(label)
                    res = api_src.deletePostId(post_id)
                    logging.info(f"State: {api_src.getClient().state}")
                logging.info(f"Res: {res}")
                if "Fail!" not in res:
                    logging.info(f"Email {post_id} processed successfully.")
                    return  # Success
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} of {max_retries + 1} failed: {e}")
                if attempt < max_retries:
                    logging.info("Retrying to connect to the email server...")

                    rules = rules or moduleRules.from_config()
                    logging.info(f"Source: {source_name}")
                    source_details = rules.more.get(source_name, {})
                    api_src = rules.readConfigSrc("", source_name, source_details)
                    if label:
                        api_src.setChannel(label)
                else:
                    logging.error(
                        f"Could not delete email {post_id} after {max_retries + 1} attempts: {e}"
                    )
                    return  # Exit after last attempt failure


def _is_post_too_old(args, time_difference):
    """Checks if an email is too old and confirms processing if interactive."""
    if time_difference.days > 7:
        if args.interactive:
            confirmation = input(
                f"The post has {time_difference.days} days. Do you want to process it? (y/n): "
            )
            if confirmation.lower() != "y":
                return True
        else:
            if args.verbose:
                print(f"Too old ({time_difference.days} days), skipping.")
            return True
    return False


def _process_common_flow(
    args, model, items, metadata_extractor, content_extractor, item_cleaner=None, rules=None
):
    """
    Common flow for processing items (emails, web pages).

    metadata_extractor: func(item, index) -> (post_id, post_title, post_date)
    content_extractor: func(item, index, post_date_time, post_title) -> content_text
    item_cleaner: func(item, index, post_id) -> void
    """
    processed_any_event = False
    for i, item in enumerate(items):
        # 1. Metadata
        post_id, post_title, post_date = metadata_extractor(item, i)

        print(f"Processing Title: {post_title}", flush=True)

        # 2. Check Age
        post_date_time, time_difference = _get_post_datetime_and_diff(post_date)
        if _is_post_too_old(args, time_difference):
            continue

        # 3. Content
        content_text = content_extractor(item, i, post_date_time, post_title)
        if not content_text:
            continue

        # 4. Save & Print (Common)
        write_file(f"log/{post_id}_text.txt", content_text)
        if args.verbose:
            print_first_10_lines(content_text, "content")

        # 5. Process with LLM
        processed_event, calendar_result = _process_event_with_llm_and_calendar(
            args, model, content_text, post_date_time, post_id, post_title, rules=rules
        )

        # processed_event = True

        if processed_event:
            processed_any_event = True
            # 6. Post-process
            if item_cleaner:
                item_cleaner(item, i, post_id)

    return processed_any_event


def process_txt_cli(args, model, source_name=None, rules=None):
    """Processes txt files and creates calendar events."""

    if not source_name:
        source_name = input(
            f"Enter filenames separated by spaces (leave empty to use {config.MSG_TXT_DIR}): "
        ).split()
        if not source_name:
            print(f"No filenames entered. Extracting texts from {config.MSG_TXT_DIR}...")

    api_src, posts = _get_msgs_from_folder(args, source_name, rules=rules)

    if posts:

        def metadata_extractor(post, i):
            # Use getPostIdM if it exists, otherwise use getPostId
            if hasattr(api_src, "getPostIdM"):
                post_id = api_src.getPostIdM(post)
            else:
                post_id = post[0]

            # print(f"Post id: {post_id}")
            # print(f"Post id: {post_id}")
            lines_txt = post[1].split("\n")
            import re

            date = ""
            for line in reversed(lines_txt):
                match = re.search(r"(?i)date:\s*([^\s\n]+)", line)
                if match:
                    date = match.group(1)
                    break

            if not date and len(lines_txt) > 1:
                last_line = lines_txt[-1].strip() or lines_txt[-2].strip()
                if last_line:
                    parts = last_line.split(": ")
                    if len(parts) > 1:
                        date = "".join(parts[1:])

            if not date and len(lines_txt) > 1:
                date = lines_txt[1].split(" ")[-1]

            if " " in date:
                date = date.split(" ")[0]

            if not args.interactive:
                date = datetime.datetime.today()

            if "Subject: " in lines_txt:
                title = next((i for i, s in enumerate(lines_txt) if "Subject: " in s), -1)
            else:
                title = lines_txt[0]
            logging.info(f"Extracted info. PostId: {post_id} Title: {title} Date: {date}")
            return post_id, title, date

        def content_extractor(post, i, post_date_time, post_title):
            lines_txt = post[1].split("\n")
            if "Subject: " in lines_txt:
                post_title = next((i for i, s in enumerate(lines_txt) if "Subject: " in s), -1)
            else:
                post_title = lines_txt[0]
            full_email_content = "".join(lines_txt[3:-1])
            date_message = lines_txt[-1].split(" ")[-1]
            # FIXME is this ok?
            date_message = datetime.datetime.today()
            return (
                f"Subject: {post_title}\n"
                f"Message: {full_email_content}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            pass

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
        )
    return False  # Default return if something went wrong before the main logic


def process_email_cli(args, model, source_name=None, api_src=None, rules=None):
    """Processes emails and creates calendar events."""

    if not api_src:
        if source_name:
            rules = rules or moduleRules.from_config()
            api_src = select_api(args, "gmail", rules=rules)
            #source_details = rules.more.get(source_name, {})
            # print(f"Sourceeee: {source_details}")
            #api_src = rules.readConfigSrc("", source_name, source_details)
        else:
            api_src = select_api(args, "email", rules=rules)
    else:
        api_src = rules.readConfigSrc("", api_src, None)


    posts = _get_emails_from_folder(args, api_src)

    if posts:

        def metadata_extractor(post, i):
            # Use getPostIdM if it exists, otherwise use getPostId
            if hasattr(api_src, "getPostIdM"):
                post_id = api_src.getPostIdM(post)
            else:
                post_id = api_src.getPostId(post)
            return post_id, api_src.getPostTitle(post), api_src.getPostDate(post)

        def content_extractor(post, i, post_date_time, post_title):
            full_email_content = api_src.getPostBody(post)
            date_message = str(post_date_time).split(" ")[0]
            return (
                f"Subject: {post_title}\n"
                f"Message: {full_email_content}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            if "imap" in api_src.service.lower():
                post_pos = i + 1
            else:
                post_pos = post_id
            _delete_email(args, api_src, post_pos, source_name, rules=rules)

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
        )
    return False  # Default return if something went wrong before the main logic


def _get_pages_from_urls(args, urls):

    page = moduleHtml.moduleHtml()
    if args.verbose:
        print(f"Urls: {urls}")
    page.setUrl(urls)
    page.setApiPosts()
    posts = page.getPosts()

    if not posts:
        print(f"There are no posts with these urls {urls}")
        posts = None

    return page, posts


def _get_links_from_notes():
    """Extracts URLs from all notes in ~/notes."""
    try:
        from note_app import NoteManager

        notes_dir = os.path.expanduser("~/notes")
        if not os.path.exists(notes_dir):
            logging.warning(f"Notes directory {notes_dir} does not exist.")
            return {}

        manager = NoteManager(storage_dir=notes_dir)
        titles = manager.list_notes()
        url_to_notes = {}
        for title in titles:
            note = manager.read_note(title)
            if note:
                # get_urls() returns explicitly added URLs
                # get_links() returns URLs extracted from content
                note_urls = set(note.get_urls()) | set(note.get_links())
                for url in note_urls:
                    if url not in url_to_notes:
                        url_to_notes[url] = []
                    url_to_notes[url].append(title)
        return url_to_notes
    except ImportError:
        logging.warning("note_app not found. Cannot extract links from notes.")
        return {}
    except Exception as e:
        logging.error(f"Error extracting links from notes: {e}")
        return {}


def process_web_cli(args, model, urls=None, force_refresh=False, rules=None):
    """Processes web pages and creates calendar events."""

    url_to_notes = {}
    urls_input = None
    if not urls:
        if args.interactive:
            urls_input = input(
                "Enter URLs separated by spaces (leave empty to use ~/notes): "
            ).split()
        if not urls_input or not args.interactive:
            print("No URLs entered. Extracting links from ~/notes...")
            url_to_notes = _get_links_from_notes()
            if not url_to_notes:
                print("No links found in ~/notes.")
                return False
            print(f"Found notes: {url_to_notes}")
            urls = list(url_to_notes.keys())
            print(f"Found total of links: {len(urls)}")
            print(f"Found links: {urls}")
        else:
            urls = urls_input

    api_src, posts = _get_pages_from_urls(args, urls)

    if posts:
        # Instantiate manager if we might need to delete notes
        manager = None
        if url_to_notes:
            try:
                from note_app import NoteManager

                notes_dir = os.path.expanduser("~/notes")
                manager = NoteManager(storage_dir=notes_dir)
            except ImportError:
                pass

        def metadata_extractor(post, i):
            title = api_src.getPostTitle(post)
            if not title:
                title = urls[i]

            # Generate a safe, readable filename from the URL
            import re

            from .web import extract_domain_and_path_from_url

            processed_url = extract_domain_and_path_from_url(urls[i])
            # Replace unsafe characters with underscores
            safe_id = re.sub(r"[^a-zA-Z0-9.-]", "_", processed_url)

            hash_value = hash(urls[i])

            # Truncate to a safe length (e.g., 150 chars) to avoid "File name
            # too long" errors
            if len(safe_id) > 130:
                safe_id = safe_id[:130]
            safe_id = f"{safe_id}_{hash_value}"

            return safe_id, title, datetime.datetime.now()

        def content_extractor(post, i, post_date_time, post_title):
            web_content_reduced = reduce_html(urls[i], post, force_refresh=force_refresh)
            if not web_content_reduced:
                print(f"Could not process {urls[i]}, skipping.")
                return None

            date_message = str(post_date_time).split(" ")[0]
            return (
                f"Url: {urls[i]}\n"
                f"Subject: {post_title}\n"
                f"Message: {web_content_reduced}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            url = urls[i]
            if url in url_to_notes and manager:
                for note_title in url_to_notes[url]:
                    print(f"Deleting note: {note_title}")
                    manager.delete_note(note_title)

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
        )

    return False  # Default return if something went wrong before the main logic


def add_events_cli(args, rules=None):
    """Add entries to the calendar from various sources (email, web, text)."""
    rules = rules or moduleRules.from_config()

    model = select_llm(args)

    print(f"Selected model: {model.model_name}")

    sources, more_options = get_add_sources(rules=rules)
    if args.verbose:
        print(f"Source: {args.source}")
        print(f"Sources: {sources}")
        print(f"More options: {more_options}")
    if args.source:
        matches = [item for item in sources if args.source in item] 
        if not matches and more_options: 
            matches = [item for item in more_options if args.source in str(item)]
    if args.interactive:
        sel, selected = select_from_list(sources, more_options=more_options, title="Sources of information")
        # selected = rules.selectRuleInteractive(
        #     sources, title="Select Rule", more_options=more_options
        # )
    else:
        selected = matches[0] if matches else None
    if selected:
        print(f"\nSelected source: {selected}")
        if hasattr(selected, "__iter__") and (
            ("web" in str(selected)) or ("http" in str(selected))
        ):
            url_list = None
            if isinstance(selected, str) and "http" in selected:
                url_list = selected.split(" ")
            process_web_cli(
                args, model, urls=url_list, force_refresh=args.force_refresh, rules=rules
            )
        elif hasattr(selected, "__iter__") and (
                ("text" in str(selected)) or os.path.exists(str(selected))):
            file_list = None
            if isinstance(selected, str) and "." in selected:
                file_list = selected.split(" ")
            process_txt_cli(args, model, source_name=file_list, rules=rules)
        else:
            process_email_cli(args, model, source_name=args.source, api_src=selected, rules=rules)
