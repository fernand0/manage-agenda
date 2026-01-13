# Reference to commit 1007c4a5 regarding api_src.deletePostId(post_id)

The commit 1007c4a56c0cb37a689f7970d35b0d4c220a5ecd from Thu Oct 16 19:02:04 2025
introduced the instruction:

    res = api_src.deletePostId(post_id)

as part of a refactoring effort to update email processing logic. This replaced the
previous IMAP flag-based deletion approach with the simpler deletePostId method.
