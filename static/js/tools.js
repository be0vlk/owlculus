function runTool(form) {
    event.preventDefault();
    var formData = new FormData(form);
    var toolName = form.getAttribute('data-tool');
    var loader = form.querySelector('.loader');
    var outputContainer = form.parentNode.querySelector('.output-container');
    const csrfToken = getCsrfCookie();

    loader.style.display = 'block';
    outputContainer.innerHTML = '';

    var requestData = {
        tool: formData.get('tool'),
        target: formData.get('target'),
        case_number: formData.get('case_number')
    };

    var eventSource = new EventSource('/tools?' + new URLSearchParams(requestData));
    form.eventSource = eventSource;

    eventSource.onmessage = function(event) {
        var outputElement = document.createElement('pre');
        outputElement.textContent = event.data;
        outputContainer.appendChild(outputElement);
        outputContainer.scrollTop = outputContainer.scrollHeight; // Auto-scroll to the bottom
    };

    eventSource.onerror = function(error) {
        console.error('Error:', error);
        loader.style.display = 'none';
        var errorElement = document.createElement('p');
        errorElement.textContent = 'An error occurred while running the tool.';
        outputContainer.appendChild(errorElement);
        eventSource.close();
    };

    eventSource.addEventListener('close', function() {
        loader.style.display = 'none';
        eventSource.close();
    });

    fetch('/tools', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(requestData)
    });
}

function cancelTool(button) {
    var form = button.closest('form');
    var eventSource = form.eventSource;

    if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
        var confirmCancel = confirm("Are you sure you want to cancel the tool execution?");
        if (confirmCancel) {
            eventSource.close();
            var loader = form.querySelector('.loader');
            loader.style.display = 'none';
            var outputContainer = form.parentNode.querySelector('.output-container');
            var cancelMessage = document.createElement('p');
            cancelMessage.textContent = 'Tool execution canceled.';
            outputContainer.appendChild(cancelMessage);
        }
    }
}

function uploadFile(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const csrfToken = getCsrfCookie();

    fetch('/tools/strixy/upload', {
        method: 'POST',
        headers: {
            'X-CSRF-Token': csrfToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.file_id) {
            const fileSelect = document.getElementById('file_id');
            const option = document.createElement('option');
            option.value = data.file_id;
            option.text = formData.get('file').name;
            fileSelect.add(option);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function runStrixy(form) {
    event.preventDefault();
    const formData = new FormData(form);
    const loader = form.querySelector('.loader');
    const outputContainer = form.parentNode.querySelector('.output-container');
    const csrfToken = getCsrfCookie();

    loader.style.display = 'block'; // Show the spinner
    outputContainer.innerHTML = ''; // Clear previous output

    const requestData = {
        query: formData.get('query'),
        new_thread: formData.get('new_thread') === 'on',
        file_ids: formData.get('file_id') ? [formData.get('file_id')] : undefined,
    };

    fetch('/tools/strixy', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        loader.style.display = 'none';
        const responseElement = document.createElement('pre');
        responseElement.textContent = data.response;
        outputContainer.appendChild(responseElement);
    })
    .catch(error => {
        console.error('Error:', error);
        loader.style.display = 'none';
        const errorElement = document.createElement('p');
        errorElement.textContent = 'An error occurred while running Strixy.';
        outputContainer.appendChild(errorElement);
    });
}

function makeStrixyRequest(requestData, loader, outputContainer, csrfToken) {
    fetch('/tools/strixy', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        loader.style.display = 'none';
        const outputElement = document.getElementById('strixy-output');
        outputElement.innerHTML = ''; // Clear previous output
        outputElement.textContent = data.response;
    })
    .catch(error => {
        console.error('Error:', error);
        loader.style.display = 'none';
        const errorElement = document.createElement('p');
        errorElement.textContent = 'An error occurred while running Strixy.';
        outputContainer.appendChild(errorElement);
    });
}

function fetchFiles() {
    const csrfToken = getCsrfCookie();
    fetch('/tools/strixy/files', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        var fileSelect = document.getElementById('file_id');
        data.forEach(file => {
            var option = document.createElement('option');
            option.value = file.id;
            option.text = file.filename;
            fileSelect.add(option);
        });
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function toggleStrixy() {
    var strixybody = document.getElementById('strixy-body');
    if (strixybody.hidden) {
        strixybody.hidden = false;
        fetchFiles();
    } else {
        strixybody.hidden = true;
    }
}