"""List VISA resources visible to PyVISA."""

from scopes_tool_core.visa_backend import list_visa_resources


def main() -> None:
    listing = list_visa_resources()
    print(f"PyVISA backend: {listing.backend}")
    print("Resources:")
    for resource in listing.resources:
        print(f"  {resource}")


if __name__ == "__main__":
    main()
