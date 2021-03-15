$(document).ready(function () {
    $('.start').click(function () {
        let start_button = $(this);
        let stop_button = start_button.parent().parent().children().eq(1).children().eq(0);
        let status_div = stop_button.parent().parent().parent().parent().children().eq(0).children().eq(0).children().eq(2);
        let start_url = start_button.data('start-url');

        status_div.removeClass('text-warning').addClass('text-success');
        status_div.text('Running');

        $.ajax({
            url: start_url,
            type: 'GET',
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                if (data.task_id) {
                    start_button.prop('disabled', true);
                    stop_button.prop('disabled', false);
                }
            },
        });
        return false;
    });
    $('.stop').click(function () {
        let stop_button = $(this);
        let start_button = stop_button.parent().parent().children().eq(0).children().eq(0);
        let status_div = stop_button.parent().parent().parent().parent().children().eq(0).children().eq(0).children().eq(2);
        let stop_url = stop_button.data('stop-url');

        console.log(status_div);

        status_div.removeClass('text-success').addClass('text-warning');
        status_div.text('Stopping');

        $.ajax({
            url: stop_url,
            type: 'GET',
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                start_button.prop('disabled', true);
                stop_button.prop('disabled', true);

            },
        });
        return false;
    })
});
