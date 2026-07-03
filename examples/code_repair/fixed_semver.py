def sort_versions(versions):
    """Return versions sorted by SemVer precedence using only stdlib."""

    def prerelease_key(prerelease):
        if prerelease == "":
            return (1,)

        parts = []
        for item in prerelease.split("."):
            if item.isdigit():
                parts.append((0, int(item)))
            else:
                parts.append((1, item))
        return (0, tuple(parts))

    def key(version):
        core, _, _build = version.partition("+")
        main, _, prerelease = core.partition("-")
        major, minor, patch = [int(part) for part in main.split(".")]
        return (major, minor, patch, prerelease_key(prerelease))

    return sorted(versions, key=key)
