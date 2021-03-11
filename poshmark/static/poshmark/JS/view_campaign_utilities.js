$(document).ready(function () {
    $('.start').click(function () {
        let start_button = $(this);
        let stop_button = start_button.parent().parent().children().eq(1).children().eq(0);
        let start_url = start_button.data('start-url');

        $.ajax({
            url: start_url,
            type: 'GET',
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                console.log(data);
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
        let start_button = start_button.parent().parent().children().eq(0).children().eq(0);
        let stop_url = start_button.data('stop-url');

        $.ajax({
            url: stop_url,
            type: 'GET',
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                console.log(data.revoked);
                if (data.task_id) {
                    console.log('something@')
                }
                start_button.prop('disabled', false);
                stop_button.prop('disabled', true);
            },
        });
        return false;
    })
});
