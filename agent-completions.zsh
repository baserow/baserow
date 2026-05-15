# Zsh completions for `just agent` / `j agent`.
# Source from .zshrc:  source /path/to/baserow/agent-completions.zsh

_baserow_agent_complete() {
    local root
    root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" 2>/dev/null)" || return

    local cmds=(infra-up infra-down up open down clean logs exec list)
    local name_cmds=(up open down clean logs exec)

    # Determine position: "just agent <cmd> <name> ..."
    # Account for both "just" and "j" as the first word
    local cmd_word name_word
    if [[ "${words[2]}" == "agent" ]]; then
        cmd_word="${words[3]}"
        name_word="${words[4]}"
    else
        return
    fi

    # Completing the subcommand (3rd word)
    if (( CURRENT == 3 )); then
        _describe 'agent command' cmds
        return
    fi

    # Completing the name (4th word)
    if (( CURRENT == 4 )); then
        # Only for commands that take a name
        if (( ${name_cmds[(Ie)$cmd_word]} )); then
            local worktrees=()
            local wt_dir="$root/.claude/worktrees"
            if [[ -d "$wt_dir" ]]; then
                worktrees=("${(@f)$(ls "$wt_dir" 2>/dev/null)}")
            fi

            # For "up", also offer branch names (new worktrees)
            if [[ "$cmd_word" == "up" ]]; then
                local branches=("${(@f)$(git -C "$root" branch --format='%(refname:short)' 2>/dev/null)}")
                _alternative \
                    "worktrees:existing worktree:compadd -a worktrees" \
                    "branches:git branch:compadd -a branches"
            else
                compadd -a worktrees
            fi
        fi
        return
    fi

    # Completing service names for logs/exec (5th word)
    if (( CURRENT == 5 )) && [[ "$cmd_word" == "logs" || "$cmd_word" == "exec" ]]; then
        local services=(backend web-frontend celery redis caddy mjml-email-compiler)
        compadd -a services
        return
    fi
}

# Hook into just/j completion
if (( ${+functions[_just]} )); then
    # Wrap the existing _just completer
    functions[_baserow_orig_just]="${functions[_just]}"

    _just() {
        if [[ "${words[2]}" == "agent" ]]; then
            _baserow_agent_complete
        else
            _baserow_orig_just "$@"
        fi
    }
fi
