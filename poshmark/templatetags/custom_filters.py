import pytz

from django import template
from django.template.defaultfilters import stringfilter
from poshmark.models import PoshUser,LogEntry

register = template.Library()


@register.filter
def status_return(status_code):
    """Takes a status code and returns it's message"""
    status = {
        PoshUser.INUSE: 'In Use',
        PoshUser.ACTIVE: 'Active',
        PoshUser.INACTIVE: 'Inactive',
        PoshUser.WALIAS: 'Waiting for alias email to be verified',
        PoshUser.WREGISTER: 'Waiting to be registered',
        PoshUser.REGISTERING: 'Registering',
        PoshUser.UPROFILE: 'Updating Profile',
    }

    return status[status_code]


@register.filter
def status_color_return(status_code):
    """Takes a status code and returns it's message"""
    statuses = {
        PoshUser.INUSE: 'border-dark',
        PoshUser.ACTIVE: 'border-success',
        PoshUser.INACTIVE: 'border-secondary',
        PoshUser.WALIAS: 'border-primary',
        PoshUser.WREGISTER: 'border-warning',
        PoshUser.REGISTERING: 'border-info',
        PoshUser.UPROFILE: 'border-danger',
    }

    return statuses[status_code]


@register.filter
def gender_return(status_code):
    """Takes a gender code and returns it's gender"""
    status = {
        '0': 'Unspecified',
        '1': 'Female',
        '2': 'Male',
    }

    return status[status_code]


@register.filter
def log_entry_return(log_entry):
    """Takes a log entry and returns a formatted message"""
    log_levels = {
        LogEntry.CRITICAL: 'CRITICAL',
        LogEntry.ERROR: 'ERROR',
        LogEntry.WARNING: 'WARNING',
        LogEntry.INFO: 'INFO',
        LogEntry.DEBUG: 'DEBUG',
        LogEntry.NOTSET: 'NOTSET',
    }
    local_tz = pytz.timezone('US/Eastern')
    timestamp = log_entry.timestamp
    localized_timestamp = timestamp.astimezone(local_tz)
    timestamp_str = localized_timestamp.strftime('%Y-%m-%d %I:%M:%S %p')

    return f'{timestamp_str} [{log_levels[log_entry.level]}] {log_entry.message}'


@register.filter
def level_color_return(level):
    """Takes a status code and returns it's message"""
    colors = {
        LogEntry.CRITICAL: 'text-danger',
        LogEntry.ERROR: 'text-danger',
        LogEntry.WARNING: 'text-warning',
        LogEntry.INFO: 'text-dark',
        LogEntry.DEBUG: 'text-info',
        LogEntry.NOTSET: 'text-dark',
    }

    return colors[level]


@register.filter
@stringfilter
def split(value, sep):
    """Takes a string and splits it into a list by spe"""
    return value.split(sep)


@register.filter
@stringfilter
def campaign_status_return(value):
    """Takes a string which is a campaign status code and returns a readable format"""
    statuses = {
        '1': 'RUNNING',
        '2': 'IDLE',
        '3': 'Stopping',
    }

    return statuses[value]


@register.filter
@stringfilter
def campaign_color_return(value):
    """Takes a string which is a campaign status code and returns a class for text color"""
    statuses = {
        '1': 'text-success',
        '2': 'text-warning',
        '3': 'text-warning',
    }

    return statuses[value]


@register.filter
def time_return(value, period):
    """Takes a time as int and adds the period to it(AM or PM)"""
    period = 'AM' if period == '0' or period == '1' else 'PM'
    value = 12 if value == 0 else value

    value = value if len(str(value)) == 2 else f'0{value}'

    return f'{value} {period}'


@register.filter
def logger_type_return(logger_type):
    """Takes a logger type code and returns it the type"""

    logger_types = {
        '0': 'other',
        '1': 'registration',
        '2': 'campaign',
    }
    return logger_types[logger_type] if logger_type in logger_types.keys() else 'Other'


@register.filter
def get_username(posh_user_id):
    """Given a Posh User ID will return the username"""
    return PoshUser.objects.get(id=posh_user_id).username
