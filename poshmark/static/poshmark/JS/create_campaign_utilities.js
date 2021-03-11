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
    };
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
        return /^\d*$/.test(value);    // Allow digits only, using a RegExp
    });
    $('.basicAutoSelect').autoComplete();
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
                    if (value === current_button.text()) {
                       times_added_list.splice(index, 1)
                    }
                });

                input_field.val("");
                input_field.val(times_added_list);
            }
        }
    });
    $('#add_listing').click(function () {
        let listings_field = $('#id_listings');
        let listing_ids = listings_field.val();
        let listing_ids_list = listing_ids.split(',');
        let listing_input_field = $('#listing_input');
        let listing_text = listing_input_field.val();
        let divider = listing_text.indexOf(' | ');
        let listing_id = listing_text.substring(divider + 3, listing_text.length);
        let listing_name = listing_text.substring(0, divider);
        let listings_container = $('#listings_container');
        let container = document.createElement('LI');
        let row = document.createElement('DIV');
        let col1 = document.createElement('DIV');
        let col2 = document.createElement('DIV');
        let listing = document.createElement('P');
        let delete_button = document.createElement('BUTTON');

        if (!(divider === -1)){
            listing_input_field.val('');
            if (!listing_ids_list.includes(listing_id)) {
                if (listing_ids) {
                    listing_ids = listing_ids.concat(',', listing_id)
                } else {
                    listing_ids = listing_id
                }

                listings_field.val("");
                listings_field.val(listing_ids);

                $(container).addClass('list-group-item');
                $(row).addClass('row');
                $(row).addClass('justify-content-between');
                $(col1).addClass('col');
                $(col2).addClass('col');
                $(listing).addClass('m-0');
                $(listing).text(listing_name);
                $(delete_button).html('&times;');
                $(delete_button).addClass('close');
                $(delete_button).attr('type', 'button');
                $(delete_button).attr('aria-label', 'Close');
                $(delete_button).attr('id', listing_id);
                $(delete_button).click(deleteListing);

                $(col1).append(listing);
                $(col2).append(delete_button);
                $(row).append(col1);
                $(row).append(col2);

                $(container).append(row);
                listings_container.append(container);
            } else {
               alert(listing_name.concat(' is already part of this campaign.'))
            }
        }

    });

});
