# wraith

> **n.** *A ghost that haunts your `$HOME` directory, keeping your dotfiles in order.*

`wraith` is a minimalist, git-based dotfiles manager. You write a `Wraithfile`, point it at your config files, and wraith symlinks them into `$HOME`. Track the repo in git, clone it anywhere, run `wraith install`, and your entire environment materializes.

---

## Quick Start

```bash
# Clone (or create) your dotfiles repo
git clone https://github.com/YOUR_USER/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Write a Wraithfile (see below)
cp Wraithfile.example Wraithfile
$EDITOR Wraithfile

# Install your dotfiles
wraith install

# On a new machine — one command to feel at home
git clone https://github.com/YOUR_USER/dotfiles.git ~/dotfiles
cd ~/dotfiles && wraith install
```

---

## The Wraithfile

One entry per line: `<source in repo> -> <destination in $HOME>`

```
bash/.bashrc       -> ~/.bashrc
bash/.profile      -> ~/.profile
vim/vimrc          -> ~/.vim/vimrc
git/.gitconfig     -> ~/.gitconfig
```

Paths are relative to the repo root. `~` is expanded to `$HOME`. Blank lines and `#` comments are ignored.

---

## Commands

| Command | Description |
|---|---|
| `wraith install` | Symlink all tracked dotfiles into `$HOME` (backs up existing files) |
| `wraith status` | Show link status of every tracked dotfile |
| `wraith list` | List all tracked source files |
| `wraith add <src> [dest]` | Append a new entry to the Wraithfile |
| `wraith init <dir>` | Scaffold a new wraith repo with an empty Wraithfile |

---

## Installation

### From PyPI (eventually)

```bash
pip install wraith-dotfiles
```

### From source

```bash
pip install .
```

### Bootstrap script

For a new machine, you only need this:

```bash
# Clone your dotfiles
git clone https://github.com/EddieMayhem/dotfiles.git ~/dotfiles
cd ~/dotfiles

# If wraith isn't installed yet, get it:
pip install .

# Now install everything
wraith install
```

---

## Design Principles

- **No agent, no daemon.** Plain symlinks. Git does the versioning.
- **No forced conventions.** Store your repo however you like.
- **Safe by default.** `install` backs up existing files before clobbering them.
- **Dry run.** `--dry-run` shows you exactly what would happen before it happens.

---

## Status Icons

| Icon | Meaning |
|---|---|
| `✓ linked` | Symlink is correct |
| `! modified` | File exists but is not the symlink (may need attention) |
| `? missing` | Tracked but no symlink exists |

---

## License

MIT
