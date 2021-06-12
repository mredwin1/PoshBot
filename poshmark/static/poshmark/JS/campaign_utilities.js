$(document).ready(function () {
    function deleteListing () {
        let id = $(this).attr('id');
        let listings_field = $('#id_listings');

        $(this).parent().parent().parent().remove()

        let listing_ids_list = listings_field.val().split(',');

        $(listing_ids_list).each(function (index, value) {
            if (value === id) {
                listing_ids_list.splice(index, 1)
            }
        });

        listings_field.val("");
        listings_field.val(listing_ids_list);
    }
    function highlight_selection() {
        let clicked = $(this);
        let parent = clicked.parent();
        let modal_container = $('#modal_container');
        let search_type = modal_container.data('type');

        if (search_type === 'posh_user') {
            if (clicked.hasClass('bg-primary')) {
                clicked.removeClass('bg-primary')
            } else {
                parent.children().each(function (index, value) {
                    if ($(value).hasClass('bg-primary')) {
                        $(value).removeClass('bg-primary')
                    }
                });
                clicked.addClass('bg-primary')
            }
        } else {
            if (clicked.hasClass('bg-primary')) {
                clicked.removeClass('bg-primary')
            } else {
                clicked.addClass('bg-primary')
            }
        }

    }
    function send_search(url) {
        let modal_container = $('#modal_container');
        let search_type = modal_container.data('type');
        let ids= $('#id_'.concat(search_type)).val();

        $.ajax({
            url: url,
            type: 'GET',
            cache: false,
            processData: false,
            contentType: false,
            success: function (data) {
                modal_container.html('');
                $.each(data, function (key, value) {
                    let divider_index = value.indexOf('|');
                    let username = value.substring(0, divider_index);
                    let id = value.substring(divider_index + 1, value.length);
                    let li = $(document.createElement('LI'));

                    li.addClass('list-group-item');
                    li.css('cursor', 'pointer');
                    li.text(username);
                    li.attr('id', id);
                    li.click(highlight_selection);

                    if (ids) {
                        let id_list = ids.split(',');
                        if ($.inArray(id, id_list) !== -1) {
                            li.addClass('bg-primary')
                        }
                    }

                    modal_container.append(li)
                })
            },
        });
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
    $("#id_lowest_price").inputFilter(function(value) {
        return /(^\d)/.test(value);    // Allow digits only, using a RegExp
    });
    $('.time').click( function (event) {
        let current_button = $(this);
        let input_field = $('#id_times');
        let times_added = input_field.val();

        if (event.shiftKey) {
            let found_this = false;
            let found_previous = false;
            let elements = [];

            $($('.time').get().reverse()).each(function (index, value) {
                if (found_this) {
                    if (!$(value).hasClass('btn-dark')) {
                        elements.push($(value))
                    } else {
                        $(elements).each(function (index, value) {
                            value.addClass('btn-dark').removeClass('btn-outline-dark');
                            if (times_added) {
                                times_added = times_added.concat(',', value.text())
                            } else {
                                times_added = times_added.concat(value.text())
                            }

                        });
                        input_field.val("");
                        input_field.val(times_added);
                        found_previous = true;
                        return false
                    }
                } else {
                    if (value === current_button.get()[0]) {
                        if ($(value).hasClass('btn-outline-dark')) {
                            $(value).addClass('btn-dark').removeClass('btn-outline-dark');

                            if (times_added) {
                                times_added = times_added.concat(',', $(value).text())
                            } else {
                                times_added = times_added.concat($(value).text())
                            }
                        }
                        found_this = true
                    }
                }
            });

            if (!found_previous) {
                current_button.addClass('btn-dark').removeClass('btn-outline-dark');

                input_field.val("");
                input_field.val(times_added);
            }
        } else {
            if (current_button.hasClass('btn-outline-dark')) {
                current_button.addClass('btn-dark').removeClass('btn-outline-dark');
                if (times_added) {
                    times_added = times_added.concat(',', current_button.text())
                } else {
                    times_added = current_button.text()
                }
                input_field.val("");
                input_field.val(times_added);

            } else if (current_button.hasClass('btn-dark')) {
                current_button.addClass('btn-outline-dark').removeClass('btn-dark');
                let times_added_list = times_added.split(',');

                $(times_added_list).each(function (index, value) {
                    let temp_text = current_button.text()
                    let text
                    if (temp_text.length !== 5) {
                        text = '0'.concat(temp_text)
                    } else {
                        text = temp_text
                    }
                    if (value === text) {
                        times_added_list.splice(index, 1)
                    }
                });

                input_field.val("");
                input_field.val(times_added_list);
            }
        }
    });
    $('#id_mode').change(function () {
        let mode = $(this).val();
        let listing_items = $('#listing');
        let generate_users = $('#generate_users');
        let lowest_price_label = $('#lowest_price_label')
        let lowest_price_input = $('#id_lowest_price')

        if (mode === '0') {
            listing_items.hide();
            generate_users.hide();
            lowest_price_label.show();
            lowest_price_input.show();
            lowest_price_input.prop('required', true);
        } else if (mode === '1') {
            listing_items.show();
            generate_users.show();
            lowest_price_label.hide();
            lowest_price_input.hide();
            lowest_price_input.prop('required', false);
        }
    });
    $('#mainModal').on('show.bs.modal', function (event) {
        let trigger = $(event.relatedTarget);
        let title = trigger.data('title');
        let url = trigger.data('url');
        let placeholder = trigger.data('placeholder');
        let modal = $(this);
        let save_type = trigger.data('save-type');
        let modal_container = $('#modal_container');

        modal.find('.modal-title').text(title);
        $('#modal_search').attr('placeholder', placeholder);
        modal_container.data('type', save_type);

        send_search(url.concat('?q='))

    });
    $('#modal_search').on('change textInput input',function () {
        let search = $(this).val();
        let url = $('#select_posh_user').data('url');

        send_search(url.concat('?q='.concat(search)), )
    });
    $('#save_changes').click(function () {
        let main_modal = $('#mainModal');
        let modal_container = $('#modal_container');
        let listings_container = $('#listings_container');
        let selection = main_modal.find('.bg-primary');

        if (modal_container.data('type') === 'posh_user') {
            let value_field = $('#id_posh_user');
            let username_field = $('#posh_username');
            let username_value_field = $('#id_posh_username')
            let password_value_field = $('#id_posh_password')

            username_field.val(selection.text());
            value_field.val(selection.attr('id'));
            username_value_field.val('');
            password_value_field.val('');
        } else {
            let listings_field = $('#id_listings');
            let listing_ids = '';
            let url = listings_container.data('url');

            listings_container.html('');

            listings_field.val('');
            $(selection).each(function (index, value) {
                let listing_id = $(value).attr('id');

                if (listing_ids) {
                    listing_ids = listing_ids.concat(',', listing_id)
                } else {
                    listing_ids = listing_id
                }


                listings_field.val(listing_ids);
            });

            $.ajax({
                url: url.concat('?listing_ids='.concat(listing_ids)),
                type: 'GET',
                cache: false,
                processData: false,
                contentType: false,
                success: function (data) {
                    $(listing_ids.split(',')).each(function (index, value) {
                        let listing_id = value;
                        let col = $(document.createElement('DIV'));
                        let card = $(document.createElement('DIV'));
                        let listing_img = $(document.createElement('IMG'));
                        let card_body = $(document.createElement('DIV'));
                        let card_title = $(document.createElement('H5'));
                        let price_container = $(document.createElement('P'));
                        let size_container = $(document.createElement('P'));
                        let size = $(document.createElement('SMALL'));
                        let listing_price = $(document.createElement('SMALL'));
                        let original_price = $(document.createElement('SMALL'));
                        let strike_through = $(document.createElement('S'));

                        col.addClass('col-3');
                        col.addClass('mt-2');
                        card.addClass('card');
                        listing_img.addClass('card-img-top');
                        card_body.addClass('card-body');
                        card_title.addClass('card-title');
                        price_container.addClass('card-text');
                        price_container.addClass('mb-1');
                        listing_price.addClass('font-weight-bold');
                        listing_price.addClass('mr-1');
                        original_price.addClass('text-muted');
                        size_container.addClass('card-text');
                        size.addClass('text-muted');

                        listing_img.attr('src', data[listing_id][0]);
                        listing_img.attr('alt', 'Listing Image');

                        card_title.text(data[listing_id][1]);
                        original_price.text(data[listing_id][2]);
                        listing_price.text(data[listing_id][3]);
                        size.text(data[listing_id][4]);

                        strike_through.append(original_price);
                        price_container.append(listing_price);
                        price_container.append(strike_through);
                        size_container.append(size);
                        card_body.append(card_title);
                        card_body.append(price_container);
                        card_body.append(size_container);
                        card.append(listing_img);
                        card.append(card_body);
                        col.append(card);

                        listings_container.append(col);
                    });
                }
            });
        }
        main_modal.modal('hide')
    })
    $('#poshUserModal').on('show.bs.modal', function (event) {
        let username_field = $('#id_username')
        let password_field = $('#id_password')
        let username_value_field = $('#id_posh_username')
        let password_value_field = $('#id_posh_password')

        username_field.val('')
        password_field.val('')
        username_value_field.val('')
        password_value_field.val('')

    });
    $('#save_posh_user_changes').click(function () {
        let username = $('#id_username').val()
        let password = $('#id_password').val()
        let value_field = $('#id_posh_user');
        let username_field = $('#posh_username');
        let username_value_field = $('#id_posh_username')
        let password_value_field = $('#id_posh_password')
        let modal = $('#poshUserModal')

        if (username && password) {
            value_field.val('')
            username_field.val(username)
            username_value_field.val(username)
            password_value_field.val(password)

            modal.modal('hide')
        }
    })
});