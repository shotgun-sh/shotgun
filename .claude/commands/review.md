Review the current pull request to look for things like:
Inline imports = We must remove these unless they are truly needed.
dicts being returned by services/routers that should be Pydantic Models.
Pydantic Model classes should be moved to a models.py file in the appropriate folder.
Any leftover TODOs = We need to identify these so we can create a plan to mitigate them.
Any strings that are being passed around the should be StrEnum (in Python) or an enum in Typescript.
Look for database calls made directly in a router, this is a no no, that should at least be in a Service and preferably in a Repository if it can be re-used at all.
Look for excessive database calls in a service that could be moved to a repository to be more easily shared and more DRY.
Duplicate code, or code that should be a utility so that it can be re-used and more DRY.
