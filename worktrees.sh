#!/usr/bin/env bash

# Show git worktrees for all repositories in this directory.
# Only displays repos that have more than one worktree.

set -euo pipefail

cd "$(dirname "$0")/.."

# Colour setup — disabled when output is piped
if [ -t 1 ]; then
    BOLD='\033[1m'
    CYAN='\033[36m'
    GREEN='\033[32m'
    YELLOW='\033[33m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    BOLD='' CYAN='' GREEN='' YELLOW='' DIM='' RESET=''
fi

repos_scanned=0
repos_with_worktrees=0
found_any=false

for dir in */; do
    dir="${dir%/}"

    # Skip non-git directories
    [ -e "$dir/.git" ] || continue
    repos_scanned=$((repos_scanned + 1))

    # Read porcelain output into arrays
    worktree_paths=()
    worktree_branches=()
    worktree_prunable=()

    current_path=""
    current_branch=""
    current_prunable=false

    while IFS= read -r line; do
        if [[ "$line" == worktree\ * ]]; then
            # Save previous entry if exists
            if [ -n "$current_path" ]; then
                worktree_paths+=("$current_path")
                worktree_branches+=("$current_branch")
                worktree_prunable+=("$current_prunable")
            fi
            current_path="${line#worktree }"
            current_branch=""
            current_prunable=false
        elif [[ "$line" == branch\ * ]]; then
            current_branch="${line#branch refs/heads/}"
        elif [[ "$line" == detached ]]; then
            current_branch="(detached)"
        elif [[ "$line" == prunable* ]]; then
            current_prunable=true
        fi
    done < <(git -C "$dir" worktree list --porcelain 2>/dev/null)

    # Save last entry
    if [ -n "$current_path" ]; then
        worktree_paths+=("$current_path")
        worktree_branches+=("$current_branch")
        worktree_prunable+=("$current_prunable")
    fi

    # Skip repos with only one worktree (the main checkout)
    [ "${#worktree_paths[@]}" -gt 1 ] || continue

    repos_with_worktrees=$((repos_with_worktrees + 1))

    if $found_any; then
        echo ""
    fi
    found_any=true

    count="${#worktree_paths[@]}"
    printf "${BOLD}${CYAN}╭─ %s${RESET} ${DIM}(%d worktrees)${RESET}\n" "$dir" "$count"

    # Find the longest branch name for alignment
    max_branch_len=0
    for branch in "${worktree_branches[@]}"; do
        [ "${#branch}" -gt "$max_branch_len" ] && max_branch_len="${#branch}"
    done

    for i in "${!worktree_paths[@]}"; do
        path="${worktree_paths[$i]}"
        branch="${worktree_branches[$i]}"
        prunable="${worktree_prunable[$i]}"

        prunable_tag=""
        if [ "$prunable" = "true" ]; then
            prunable_tag="  ${YELLOW}prunable${RESET}"
        fi

        printf "${CYAN}│${RESET}  ${GREEN}%-${max_branch_len}s${RESET}  ${DIM}%s${RESET}%b\n" \
            "$branch" "$path" "$prunable_tag"
    done

    printf "${CYAN}╰─${RESET}\n"
done

echo ""
if [ "$repos_with_worktrees" -eq 0 ]; then
    printf "${DIM}No repos with extra worktrees (%d repos scanned)${RESET}\n" "$repos_scanned"
else
    printf "${DIM}%d repo(s) with extra worktrees (%d total repos scanned)${RESET}\n" \
        "$repos_with_worktrees" "$repos_scanned"
fi
