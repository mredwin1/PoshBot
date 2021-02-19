$(document).ready(function() {
    function generate_posh_user_info() {
        $.ajax({
           url: $(this).attr('data-generate-url'),
           type: 'GET',
           cache: false,
           processData: false,
           contentType: false,
           success: function (data) {
               console.log(data)
           },
        });
        return false;
    }});