# Reference to issue #2 regarding time suppression in date handling

The commit 85748c7 introduced the intentional suppression of time information when adding dates to the prompt, with the commit message: 'Date in messages is only relevant, not time of message'.

This was an intentional design decision to only provide date information to the LLM for relative date processing.
