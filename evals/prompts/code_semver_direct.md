Fix this Python function. Return only a complete replacement for sort_versions as a string field named code.

Spec:
- Sort strings by SemVer precedence.
- Versions have major.minor.patch and optional prerelease after "-".
- Numeric prerelease identifiers compare numerically, not lexicographically.
- Non-numeric prerelease identifiers compare lexicographically.
- A release version sorts after all prereleases with the same major.minor.patch.
- If prerelease identifiers match up to the shorter length, the shorter prerelease has lower precedence.
- Build metadata after "+" is ignored for precedence.
- If two versions have equal precedence, preserve their original relative order.
- Use only the Python standard library.

Buggy code:

```python
def sort_versions(versions):
    def key(version):
        main, _, prerelease = version.partition("-")
        major, minor, patch = [int(part) for part in main.split(".")]
        return (major, minor, patch, prerelease == "", prerelease)

    return sorted(versions, key=key)
```
