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

    $('.delete').click(function () {
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
                    let title_elem = $('#title')
                    let title = title_elem.text()
                    let index = title.indexOf(' ')
                    let number = parseInt(title.substring(0, index)) - 1
                    let new_title;

                    if (number === 1) {
                        new_title = number.toString().concat(' Listing')
                    } else {
                        new_title = number.toString().concat(' Listings')
                    }

                    title_elem.text(new_title)

                    delete_button.closest('div.listing-container').remove()
                },
                error: function (data) {
                    alert('An error occurred while trying to delete')
                }
            });
        }
    })
});