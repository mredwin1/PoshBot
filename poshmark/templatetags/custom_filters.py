from django import template

register = template.Library()


@register.filter
def status_return(status_code):
    """Takes a status code and returns it's message"""
    status = {
        '0': 'In Use',
        '1': 'Active',
        '2': 'Inactive',
        '3': 'Waiting for alias email to be verified',
        '4': 'Waiting to be registered',
        '5': 'Registering',
    }

    return status[status_code]


@register.filter
def status_color_return(status_code):
    """Takes a status code and returns it's message"""
    statuses = {
        '0': 'border-warning',
        '1': 'border-success',
        '2': 'border-secondary',
        '3': '.border-primary',
        '4': 'border-warning',
        '5': 'border-info',
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
