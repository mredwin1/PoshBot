$(document).ready(function () {
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
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
        let start_url = start_button.data('start-url');
        if (start_url) {
            $.ajax({
                url: start_url,
                type: 'GET',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {
                        let status_span = start_button.closest('div.campaign-container').find('span.status')

                        status_span.removeClass('text-secondary').addClass('text-info')
                        status_span.text('STARTING')
                    } else if (data.error) {
                        alert(data.error)
                    }
                },
            });
        }
    });
    $('.stop').click(function () {
        let stop_button = $(this);
        let stop_url = stop_button.data('stop-url');

        if (stop_url){
            $.ajax({
                url: stop_url,
                type: 'GET',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {
                        let status_span = stop_button.closest('div.card').find('span.status')

                        status_span.removeClass('text-success').addClass('text-warning')
                        status_span.text('STOPPING')
                    } else if (data.error) {
                        alert(data.error)
                    }
                },
            });
        }
    });
    $('#start_all').click(function () {
        let campaigns = $('.campaign-container')

        let ids = []

        $.each(campaigns, function (index, value) {
            let campaign = $(value)
            let id = campaign.data('id')
            let status = campaign.find('span.status').text()
            if (status === 'IDLE') {
                if (id) {
                    ids.push(id)
                }
            }
        })

        if (ids.length) {
            let start_url = '/start-campaigns/' + ids.join() + '/'
            $.ajax({
                url: start_url,
                type: 'GET',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {
                        let started_campaigns = data.success.split(',')

                        $.each(started_campaigns, function (index, value) {
                            let locator = '*[data-id="' + value.toString() + '"]'
                            let campaign = $(locator)
                            let status_span = campaign.find('span.status')

                            status_span.removeClass('text-secondary').addClass('text-info')
                            status_span.text('STARTING')
                        })

                    } else if (data.error) {
                        alert(data.error)
                    }
                },
            });
        }

    })
    $('#stop_all').click(function () {
        let campaigns = $('.campaign-container')

        let ids = []

        $.each(campaigns, function (index, value) {
            let campaign = $(value)
            let id = campaign.data('id')
            let status = campaign.find('span.status').text()
            if (status === 'RUNNING') {
                if (id) {
                    ids.push(id)
                }
            }
        })

        if (ids.length) {
            let start_url = '/stop-campaigns/' + ids.join() + '/'
            $.ajax({
                url: start_url,
                type: 'GET',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {
                        let stopped_campaigns = data.success.split(',')

                        $.each(stopped_campaigns, function (index, value) {
                            let locator = '*[data-id="' + value.toString() + '"]'
                            let campaign = $(locator)
                            let status_span = campaign.find('span.status')

                            status_span.removeClass('text-success').addClass('text-warning')
                            status_span.text('STOPPING')
                        })

                    } else if (data.error) {
                        alert(data.error)
                    }
                },
            });
        }

    })
    $('#delete_campaign').click(function () {
        let message = $(this).data('message')
        if (confirm(message)) {
            let delete_url = $(this).data('url')
            let delete_button = $(this)
            $.ajax({
                url: delete_url,
                type: 'POST',
                headers: { "X-CSRFToken": getCookie("csrftoken") },
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    let new_title;
                    let status = delete_button.closest('div.card').find('span.status').text()
                    let title_elem = $('#title')
                    let title = title_elem.text()
                    let slash_index = title.indexOf('/')
                    let space_index = title.indexOf(' ')
                    let running = parseInt(title.substring(0, slash_index))
                    let total = parseInt(title.substring(slash_index + 1, space_index)) - 1

                    if (status !== 'IDLE') {
                        running --;
                    }

                    new_title = running.toString().concat('/').concat(total.toString().concat(' Campaigns'))
                    title_elem.text(new_title)
                    delete_button.closest('div.campaign-container').remove()
                },
                error: function (data) {
                    alert('An error occurred while trying to delete')
                }
            });
        }
    })
});