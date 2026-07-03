def sort_versions(versions):
    """Return versions sorted by SemVer precedence.

    This intentionally buggy implementation treats prerelease identifiers as
    raw strings, so alpha.10 sorts before alpha.2.
    """
    def key(version):
        main, _, prerelease = version.partition("-")
        major, minor, patch = [int(part) for part in main.split(".")]
        return (major, minor, patch, prerelease == "", prerelease)

    return sorted(versions, key=key)

