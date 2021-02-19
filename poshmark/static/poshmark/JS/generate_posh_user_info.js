function generate_posh_user_info() {
    let form = $('#PoshUserForm');
    $.ajax({
       url: form.data('generate-info-url'),
       type: 'GET',
       cache: false,
       processData: false,
       contentType: false,
       success: function (data) {
           $.each(data, function (key, value) {
                   let id = '#id_'.concat(key);
                   $(id).val(value)
               })
       },
    });
    return false;
}