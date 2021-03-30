$(document).ready(function () {
    $.fn.inputFilter = function(inputFilter) {
        return this.on("input keydown keyup mousedown mouseup select contextmenu drop", function() {
          if (inputFilter(this.value)) {
            this.oldValue = this.value;
            this.oldSelectionStart = this.selectionStart;
            this.oldSelectionEnd = this.selectionEnd;
          } else if (this.hasOwnProperty("oldValue")) {
            this.value = this.oldValue;
            this.setSelectionRange(this.oldSelectionStart, this.oldSelectionEnd);
          } else {
            this.value = "";
          }
        });
    };
    $("#id_delay").inputFilter(function(value) {
        return /(^\d*$)|(\.$)|(^\d*\.\d*$)/.test(value);    // Allow digits only, using a RegExp
    });
    $('#addBasicCampaign').click(function () {
        let modal = $('#mainModal');
        let title = $('#mainModalTitle');

        modal.modal('show');
        title.text('Add Basic Campaign');
    });
    $('#basicCampaignForm').submit(function (event) {
        event.preventDefault();

        let form = $(this);
        let main_modal = $('#mainModal');
        let data = new FormData(form.get(0));

        $.ajax({
           url: form.attr('action'),
           type: form.attr('method'),
           data: data,
           cache: false,
           processData: false,
           contentType: false,
           success: function (data) {
                main_modal.modal('hide');
                location.reload()
           },
           error: function (data) {
                $.each(data.responseJSON, function (key, value) {
                    var id = '#id_' + key;
                    var parent = $(id).parent();
                    var p = $("<p>", {id: "error_1_id_" + key, "class": "invalid-feedback"});
                    var strong = $("<strong>").text(value);

                    parent.find('p').remove();
                    p.append(strong);
                    parent.append(p);
                    p.show();


                });
           }
        });
    });
    $('.start').click(function () {
        let start_button = $(this);
        let stop_button = start_button.parent().parent().children().eq(1).children().eq(0);
        let status_div = stop_button.parent().parent().parent().parent().children().eq(0).children().eq(0).children().eq(1);
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
        let status_div = stop_button.parent().parent().parent().parent().children().eq(0).children().eq(0).children().eq(1);
        let stop_url = stop_button.data('stop-url');

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
    });
});
