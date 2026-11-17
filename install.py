#!/usr/bin/env python3
"""Install only the bundled skills and agents. Does not edit Claude settings."""
import argparse
import datetime
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parent
FILES = (
    'skills/han-project/SKILL.md', 'skills/han-handoff/SKILL.md',
    'agents/han-scout.md', 'agents/han-builder.md', 'agents/han-deep.md',
    'agents/han-reviewer.md', 'agents/han-advisor.md',
    'skills/han-resume/SKILL.md',
    'han-project-runtime/han.py',
    'han-project-runtime/han_runtime/__init__.py',
    'han-project-runtime/han_runtime/store.py',
    'han-project-runtime/han_runtime/telemetry.py',
)
SOURCES = {name: name.removeprefix('han-project-runtime/') for name in FILES if name.startswith('han-project-runtime/')}


def install(target, *, force=False, dry_run=False):
    target = Path(target).expanduser().resolve()
    destinations = [(SOURCE / SOURCES.get(name,name), target / name) for name in FILES]
    # Validate every destination before making any changes.
    for src, dst in destinations:
        if not src.is_file():
            raise ValueError(f'Missing bundled file: {src.name}')
        if dst.is_symlink() or not dst.resolve().is_relative_to(target):
            raise ValueError(f'Refusing symlink destination: {dst}')
        if dst.exists() and not dst.is_file():
            raise ValueError(f'Destination is not a file: {dst}')
    conflicts = [(src, dst) for src, dst in destinations if dst.exists() and src.read_bytes() != dst.read_bytes()]
    if conflicts and not force:
        raise ValueError('Existing files differ; no changes made. Back up/review them or use --force:\n' + '\n'.join(str(dst) for _, dst in conflicts))
    changed = [(src, dst) for src, dst in destinations if not dst.exists() or src.read_bytes() != dst.read_bytes()]
    backup = None
    if conflicts:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_root = target / 'han-project-backups'
        backup = backup_root / stamp
        if backup_root.is_symlink() or not backup.resolve().is_relative_to(target):
            raise ValueError(f'Refusing unsafe backup directory: {backup_root}')
        for _, dst in conflicts:
            saved = backup / dst.relative_to(target)
            if saved.is_symlink() or not saved.resolve().is_relative_to(target):
                raise ValueError(f'Refusing unsafe backup destination: {saved}')
    if dry_run:
        return [str(dst) for _, dst in changed]
    if conflicts:
        for _, dst in conflicts:
            saved = backup / dst.relative_to(target)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, saved)
        print(f'Backed up differing files to {backup}')
    for src, dst in changed:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return [str(dst) for _, dst in changed]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--claude-dir', type=Path, default=Path.home()/'.claude', help='Target Claude directory; use /path/to/project/.claude for project-only install')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--force', action='store_true', help='Back up and replace differing bundled files only')
    args = p.parse_args()
    try:
        files = install(args.claude_dir, force=args.force, dry_run=args.dry_run)
    except (ValueError, OSError) as e:
        p.exit(1, f'{e}\n')
    print(('Would install' if args.dry_run else 'Installed/updated') + f' {len(files)} files.')
    for filename in files:
        print(filename)
    if not args.dry_run:
        print('Open a new Claude Code session or reload agents via /agents, then invoke /han-project <task>.')


if __name__ == '__main__':
    main()
