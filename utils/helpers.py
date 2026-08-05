from flask import flash


def flash_success(msg):
    flash(msg, "success")


def flash_error(msg):
    flash(msg, "danger")


def flash_warning(msg):
    flash(msg, "warning")


def flash_info(msg):
    flash(msg, "info")


def paginate_query(query, page, per_page=15):
    return query.paginate(page=page, per_page=per_page, error_out=False)


def format_datetime(dt, fmt="%d %b %Y, %H:%M UTC"):
    if dt is None:
        return "—"
    return dt.strftime(fmt)


def status_badge_class(status):
    return {
        "Active": "badge-active",
        "Withdrawn": "badge-withdrawn",
        "Expired": "badge-expired",
        "Pending": "badge-pending",
    }.get(status, "badge-secondary")
