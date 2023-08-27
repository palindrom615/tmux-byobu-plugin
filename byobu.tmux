#!/usr/bin/env bash
#
#    byobu - wrapper script
#    Copyright (C) 2008-2009 Canonical Ltd.
#    Copyright (C) 2008-2014 Dustin Kirkland
#
#    Authors: Dustin Kirkland <kirkland@byobu.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

VERSION=5.134
PKG="byobu"
export BYOBU_BACKEND="tmux"

export CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export BYOBU_PREFIX="$CURRENT_DIR/usr"
export BYOBU_CONFIG_DIR="$HOME/.config/byobu"
export PATH="$PATH:$BYOBU_PREFIX/bin"

# All sorts of things go wrong if you don't own your $HOME dir.
# This happens under sudo, if you don't use the -H option; Byobu will
# create a bunch of files in your $HOME which will be owned by root.
if [ ! -O "$HOME" ]; then
	echo "Cannot run $PKG because [$USER] does not own [$HOME]" 1>&2
	if [ -n "$SUDO_USER" ]; then
		echo "To run $PKG under sudo, you MUST use 'sudo -H'" 1>&2
	fi
	exit 1
fi

# Source local byobu config
if [ -r "$HOME/.byoburc" ]; then
	# Ensure that this configuration is usable
	. "$HOME/.byoburc" || mv -f "$HOME/.byoburc" "$HOME/.byoburc".orig
fi
export BYOBU_CHARMAP=$(locale charmap)

. "${BYOBU_PREFIX}/lib/${PKG}/include/common"

# Store the parent tty
if eval $BYOBU_TEST tty >/dev/null 2>&1; then
	export BYOBU_TTY=$(tty)
else
	export BYOBU_TTY=$(readlink /proc/$$/fd/0)
fi

# Get the default window name
[ -n "$BYOBU_WINDOW_NAME" ] || BYOBU_WINDOW_NAME=-

# Add a version argument for debugging purposes, enter manpage for help
if [ "$#" = "1" ]; then
	case "$1" in
		-v|--version)
			echo "$PKG version $VERSION"
			if eval $BYOBU_TEST bash >/dev/null 2>&1; then
				# Check ulimits
				u=$(bash -c "ulimit -n")
				[ "$u" = "unlimited" ] || [ $u -ge 15 ] || echo "WARNING: ulimit -n is too low" 1>&2
				u=$(bash -c "ulimit -u")
				[ "$u" = "unlimited" ] || [ $u -ge 1600 ] || echo "WARNING: ulimit -u is too low" 1>&2
			fi
			exec tmux $BYOBU_ARG_VERSION
			exit 0
		;;
	esac
fi

# Sanitize the environment
byobu-janitor --force

# Set the window title if this is a TTY
if [ -t 1 ]; then
	[ -r "$BYOBU_CONFIG_DIR/statusrc" ] && . "$BYOBU_CONFIG_DIR/statusrc"
	. $BYOBU_PREFIX/lib/$PKG/ip_address
	BYOBU_TITLE=${BYOBU_ALT_TITLE:-'${USER}@${HOSTNAME:-$(hostname)} ($(__ip_address t)) - ${PKG}'}
	[ -n "$BYOBU_NO_TITLE" ] || eval printf \"\\033\]0\;${BYOBU_TITLE}\\007\"
fi

# Drop a symlink to the ssh socket in $HOME, since we can ensure that exists
if [ -S "$SSH_AUTH_SOCK" ] && [ ! -h "$SSH_AUTH_SOCK" ]; then
	ln -sf "$SSH_AUTH_SOCK" "$BYOBU_CONFIG_DIR/.ssh-agent"
	export SSH_AUTH_SOCK="$BYOBU_CONFIG_DIR/.ssh-agent"
fi

# Fallback terminfo
[ -z "$BYOBU_DEFAULT_TERM" ] && BYOBU_DEFAULT_TERM="screen"

# Color terminfo to use, if possible
[ -z "$BYOBU_COLOR_TERM" ] && BYOBU_COLOR_TERM="screen-256color"

# Check if our terminfo supports 256 colors
CAN_SHOW_COLORS=
if eval $BYOBU_TEST tput >/dev/null 2>&1; then
	if [ "$(tput colors 2>/dev/null || echo 0)" = "256" ]; then
		CAN_SHOW_COLORS=1
	fi
fi

# Check if the color terminfo is available
HAS_COLOR_TERM=
if eval $BYOBU_TEST infocmp >/dev/null 2>&1; then
	if infocmp "$BYOBU_COLOR_TERM" >/dev/null 2>&1; then
		HAS_COLOR_TERM=1
	fi
fi

# Use 256 colors if possible
if [ -n "$CAN_SHOW_COLORS" ] || [ "$COLORTERM" = "gnome-terminal" ] || [ "$TERM" = "xterm" ] || [ "$TERM" = "xterm-256color" ] || [ "$TERM" = "screen" ]; then
	[ -z "$SCREEN_TERM" ] && SCREEN_TERM="-2"
fi
if [ -z "$BYOBU_TERM" ]; then
	if [ -n "$SCREEN_TERM" -a -n "$HAS_COLOR_TERM" ]; then
		BYOBU_TERM="$BYOBU_COLOR_TERM"
	else
		BYOBU_TERM="$BYOBU_DEFAULT_TERM"
	fi
fi
BYOBU_PROFILE="$BYOBU_PREFIX/share/$PKG/profiles/tmuxrc"
# Set default window, unless user has overriden
if egrep -qs "default-command|default-shell" $HOME/.$PKG/.tmux.conf >/dev/null 2>&1; then
	DEFAULT_WINDOW=
else
	DEFAULT_WINDOW="new-session -n $BYOBU_WINDOW_NAME ${BYOBU_PREFIX}/bin/byobu-shell"
fi
sessions=$(tmux list-sessions 2>/dev/null) || true
CUSTOM_WINDOW_SET=0
if [ -s "$BYOBU_CONFIG_DIR/windows.tmux.$BYOBU_WINDOWS" ]; then
	CUSTOM_WINDOW_SET=1
	BYOBU_WINDOWS="$BYOBU_CONFIG_DIR/windows.tmux.$BYOBU_WINDOWS"
elif [ -s "$BYOBU_CONFIG_DIR/windows.tmux" ]; then
	CUSTOM_WINDOW_SET=1
	BYOBU_WINDOWS="$BYOBU_CONFIG_DIR/windows.tmux"
fi

export BYOBU_TERM

# Save session info
[ -n "$DBUS_SESSION_BUS_ADDRESS" ] && printf "DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS\n" > "$BYOBU_RUN_DIR/sockets"
[ -n "$SESSION_MANAGER" ] && printf "SESSION_MANAGER=$SESSION_MANAGER\n" >> "$BYOBU_RUN_DIR/sockets"
tmux setenv -g BYOBU_PREFIX "$BYOBU_PREFIX"
tmux setenv -g BYOBU_CONFIG_DIR "$BYOBU_CONFIG_DIR"
tmux setenv -g BYOBU_TERM "$BYOBU_TERM"
tmux setenv -g BYOBU_BACKEND "tmux"
tmux setenv -g BYOBU_BIN "$BYOBU_PREFIX/bin"
tmux setenv -g BYOBU_CHARMAP "$BYOBU_CHARMAP"
tmux setenv -g PATH "$PATH"

tmux source-file $BYOBU_PROFILE

# vi: syntax=sh ts=4 noexpandtab
