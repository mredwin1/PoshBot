setInterval(function get_log_entries() {
    let log_container = $('#LogEntriesContainer');
    $.ajax({
       url: log_container.data('get-log-entries-url'),
       type: 'GET',
       cache: false,
       processData: false,
       contentType: false,
       success: function (data) {
          console.log(data);
           if (Object.keys(data).length > 0) {
               let new_url = data.new_url;
               let messages = data.log_entry_messages;

               log_container.data('get-log-entries-url', new_url);
               console.log(log_container);
               for (let i=0; i < messages.length; i++) {
                   let container = document.getElementById('LogEntriesContainer');
                   let row = document.createElement('DIV');
                   let col = document.createElement('DIV');
                   let message = document.createElement('P');
                   let start_index = messages[i].indexOf('[') + 1;
                   let end_index = messages[i].indexOf(']');
                   let level = messages[i].substring(start_index, end_index);
                   let message_class = 'text-dark';

                   if (level === 'CRITICAL' || level === 'ERROR') {
                       message_class = 'text-danger'
                   } else if (level === 'WARNING') {
                       message_class = 'text-warning'
                   }

                   row.classList.add('row');
                   col.classList.add('col');
                   message.classList.add('m-0');
                   message.classList.add(message_class);

                   message.innerText = messages[i];

                   col.appendChild(message);
                   row.appendChild(col);
                   container.appendChild(row);
               }
           }
       },
    });
    return false;
}, 1000);

