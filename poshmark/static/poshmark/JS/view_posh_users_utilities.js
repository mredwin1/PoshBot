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
    $('#delete_posh_user').click(function () {
        let message = $(this).data('message')
        if (confirm(message)) {
            let delete_url = $(this).data('url')
            let delete_button = $(this)
            $.ajax({
                url: delete_url,
                type: 'POST',
                cache: false,
                headers: { "X-CSRFToken": getCookie("csrftoken") },
                processData: false,
                contentType: false,
                success: function (data) {
                    let title_elem = $('#title')
                    let title = title_elem.text()
                    let index = title.indexOf(' ')
                    let number = parseInt(title.substring(0, index)) - 1
                    let new_title;

                    if (number === 1) {
                        new_title = number.toString().concat(' Posh User')
                    } else {
                        new_title = number.toString().concat(' Posh Users')
                    }

                    title_elem.text(new_title)

                    delete_button.closest('div.posh-user-container').remove()
                },
                error: function (data) {

                }
            });
        }
    })
});