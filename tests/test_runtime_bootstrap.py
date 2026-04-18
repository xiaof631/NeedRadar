from pathlib import Path

from runtime_bootstrap import _reorder_repo_root_after_site_packages


def test_repo_root_moves_after_site_packages() -> None:
    repo_root = Path("/repo")
    reordered = _reorder_repo_root_after_site_packages(
        [
            "",
            "/usr/lib/python3.11",
            "/usr/lib/python3.11/site-packages",
        ],
        repo_root=repo_root,
        cwd=repo_root,
    )

    assert reordered == [
        "/usr/lib/python3.11",
        "/usr/lib/python3.11/site-packages",
        "",
    ]


def test_repo_root_stays_when_no_site_packages_exist() -> None:
    repo_root = Path("/repo")
    original = [
        "",
        "/usr/lib/python3.11",
    ]

    reordered = _reorder_repo_root_after_site_packages(
        original,
        repo_root=repo_root,
        cwd=repo_root,
    )

    assert reordered == original
