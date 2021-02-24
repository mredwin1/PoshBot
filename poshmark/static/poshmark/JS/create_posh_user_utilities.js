function is_registered () {
    let registered_field = document.getElementById('id_is_registered');
    let profile_picture_field = document.getElementById('id_profile_picture');
    let profile_picture_container = document.getElementById('div_id_profile_picture');
    let header_picture_field = document.getElementById('id_header_picture');
    let header_picture_container = document.getElementById('div_id_header_picture');
    let first_name_field = document.getElementById('id_first_name');
    let first_name_container = document.getElementById('div_id_first_name');
    let last_name_field = document.getElementById('id_last_name');
    let last_name_container = document.getElementById('div_id_last_name');
    let email_field = document.getElementById('id_email');
    let email_container = document.getElementById('div_id_email');
    let gender_field = document.getElementById('id_gender');
    let gender_container = document.getElementById('div_id_gender');
    let generate_button = document.getElementById('id_generate_info');
    let required_span = document.createElement('SPAN');

    required_span.innerText = '*';
    required_span.classList.add('asteriskField');

    registered_field.onchange = is_registered;

    let fields = [profile_picture_field, header_picture_field, first_name_field, last_name_field, email_field,
        gender_field];

    let containers = [profile_picture_container, header_picture_container, first_name_container, last_name_container,
        email_container, gender_container];

    if (registered_field.checked) {
        fields.forEach(function (item, index) {

            item.required = false;
            item.value = '';
            generate_button.disabled = true;
        });
        containers.forEach(function (item, index) {
            item.required = true;
            item.style.display = 'none';
            generate_button.disabled = false;
        });
    } else {
        fields.forEach(function (item, index) {
            item.required = true;
            let label = item.parentElement.parentElement.getElementsByTagName("label")[0];
            let required_span_here = label.getElementsByClassName('asteriskField');
            console.log(label);
            console.log(required_span_here);
            if (required_span_here.length === 0) {
                let span_clone = required_span.cloneNode(true);
                label.appendChild(span_clone)
            }

        });
        containers.forEach(function (item, index) {
            item.style.display = 'block';
        });
    }
    return false;
}

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

document.addEventListener('DOMContentLoaded', function() {
   is_registered();
}, false);
