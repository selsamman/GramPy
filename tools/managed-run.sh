#!/bin/sh

# Shared lifecycle for commands run by mac-local.sh and pi-remote.sh.
# This file is sourced after the caller has established `root` and `log`.

managed_schedule_notification() {
    managed_notify_script=${GRAMPY_NOTIFY_SCRIPT:-$root/.local/notifyhuman.sh}
    [ -x "$managed_notify_script" ] || return 0

    managed_notify_worker='
        grace=$1
        state_dir=$2
        result_file=$3
        notifier=$4
        label=$5
        status=$6
        elapsed=$7
        job_label=$8

        managed_notify_cleanup() {
            if [ -n "$job_label" ] && command -v launchctl >/dev/null 2>&1; then
                launchctl remove "$job_label" >/dev/null 2>&1 || true
            fi
        }
        trap managed_notify_cleanup EXIT

        sleep "$grace" || exit 0
        [ -d "$state_dir" ] || exit 0
        [ -f "$result_file" ] || exit 0
        "$notifier" \
            "$label completed with exit status $status after ${elapsed}s" \
            >/dev/null 2>&1 || true
    '
    if command -v launchctl >/dev/null 2>&1; then
        managed_notify_job="grampy.notify.$$.$managed_finished_epoch"
        if launchctl submit -l "$managed_notify_job" \
            -o /dev/null -e /dev/null -- \
            /bin/sh -c "$managed_notify_worker" managed-notification \
            "$managed_notify_grace" "$managed_state_dir" \
            "$managed_result_file" "$managed_notify_script" \
            "$managed_label" "$managed_finish_status" "$managed_elapsed" \
            "$managed_notify_job" >/dev/null 2>&1; then
            return 0
        fi
    fi

    if command -v setsid >/dev/null 2>&1; then
        nohup setsid /bin/sh -c "$managed_notify_worker" managed-notification \
            "$managed_notify_grace" "$managed_state_dir" \
            "$managed_result_file" "$managed_notify_script" \
            "$managed_label" "$managed_finish_status" "$managed_elapsed" '' \
            </dev/null >/dev/null 2>&1 &
    else
        nohup /bin/sh -c "$managed_notify_worker" managed-notification \
            "$managed_notify_grace" "$managed_state_dir" \
            "$managed_result_file" "$managed_notify_script" \
            "$managed_label" "$managed_finish_status" "$managed_elapsed" '' \
            </dev/null >/dev/null 2>&1 &
    fi
}

managed_finish() {
    managed_finish_status=$1
    managed_finish_reason=$2
    managed_finished_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    managed_finished_epoch=$(date '+%s')
    managed_elapsed=$((managed_finished_epoch - managed_started_epoch))
    managed_result_tmp=$managed_state_dir/.result.md.$$
    {
        printf '# Completed command\n\n'
        printf -- '- wrapper: `%s`\n' "$managed_label"
        printf -- '- started: `%s`\n' "$managed_started_at"
        printf -- '- finished: `%s`\n' "$managed_finished_at"
        printf -- '- elapsed-seconds: `%s`\n' "$managed_elapsed"
        printf -- '- exit-status: `%s`\n' "$managed_finish_status"
        [ -z "$managed_finish_reason" ] || printf -- '- outcome: `%s`\n' "$managed_finish_reason"
        printf -- '- command: `%s`\n' "$managed_command_display"
    } >"$managed_result_tmp"
    mv "$managed_result_tmp" "$managed_result_file"
    rm -f "$managed_running_file"
    rmdir "$managed_active_dir" 2>/dev/null || true
    managed_finalized=1
    managed_schedule_notification || true
    log "completed with exit status $managed_finish_status after ${managed_elapsed}s"
    log "result: $managed_result_file"
}

managed_abort() {
    managed_abort_status=$1
    managed_abort_reason=$2
    trap - 0 HUP INT TERM
    if [ -n "${managed_child_pid:-}" ]; then
        kill -TERM "$managed_child_pid" 2>/dev/null || true
        set +e; wait "$managed_child_pid" 2>/dev/null; set -e
        managed_child_pid=
    fi
    [ "${managed_finalized:-0}" -ne 0 ] || managed_finish "$managed_abort_status" "$managed_abort_reason"
    exit "$managed_abort_status"
}

managed_run() {
    managed_label=$1
    shift
    managed_raw_session_id=${CODEX_THREAD_ID:-manual}
    managed_session_id=$(printf '%s' "$managed_raw_session_id" | LC_ALL=C tr -c 'A-Za-z0-9._-' '_')
    [ -n "$managed_session_id" ] || managed_session_id=manual
    managed_state_dir=${GRAMPY_AGENT_RUN_DIR:-$root/.local/agent-runs/$managed_session_id}
    managed_active_dir=$managed_state_dir/.active
    managed_running_file=$managed_state_dir/running.md
    managed_result_file=$managed_state_dir/result.md
    managed_log_file=$managed_state_dir/run.log
    managed_notify_grace=${GRAMPY_NOTIFY_GRACE_SEC:-30}
    managed_command_display=$*
    managed_child_pid=
    managed_finalized=0
    case $managed_notify_grace in ''|*[!0-9]*) printf '[%s] GRAMPY_NOTIFY_GRACE_SEC must be a non-negative integer\n' "$managed_label" >&2; return 64;; esac
    mkdir -p "$managed_state_dir"
    if ! mkdir "$managed_active_dir" 2>/dev/null; then
        printf '[%s] another managed command is active for this session: %s\n' "$managed_label" "$managed_running_file" >&2
        return 75
    fi
    trap 'managed_abort "$?" "wrapper exited before completion"' 0
    trap 'managed_abort 129 "interrupted by SIGHUP"' HUP
    trap 'managed_abort 130 "interrupted by SIGINT"' INT
    trap 'managed_abort 143 "interrupted by SIGTERM"' TERM
    managed_started_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    managed_started_epoch=$(date '+%s')
    {
        printf '# Running command\n\n'
        printf -- '- wrapper: `%s`\n' "$managed_label"
        printf -- '- started: `%s`\n' "$managed_started_at"
        printf -- '- command: `%s`\n' "$*"
    } >"$managed_running_file"
    : >"$managed_log_file"
    log "managed state: $managed_state_dir"
    log "command output: $managed_log_file"
    "$@" >"$managed_log_file" 2>&1 &
    managed_child_pid=$!
    set +e; wait "$managed_child_pid"; managed_status=$?; set -e
    managed_child_pid=
    managed_finish "$managed_status" ""
    trap - 0 HUP INT TERM
    return "$managed_status"
}
