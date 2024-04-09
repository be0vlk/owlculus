// We need to get the csrf token in the cookie that was set on login by jwt-extended
function getCsrfCookie() {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${'csrf_access_token'}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

// Reusable way to load DataTable stuff
function initializeDataTable(selector) {
    var table = $(selector).DataTable({
        dom:
            "<'uk-flex uk-flex-between uk-flex-middle'<'uk-button-group'B><'uk-search uk-search-default'f>>" +
            "<'uk-overflow-auto'tr>" +
            "<'uk-flex uk-flex-between uk-flex-middle'<'uk-pagination'l><'uk-pagination'p>>",
        buttons: [
            {
                extend: 'csvHtml5',
                text: 'Export CSV',
                className: 'uk-button uk-button-default'
            }
        ],
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search..."
        }
    });

    // Apply custom classes for UIkit styling compatibility
    $('.dataTables_length').addClass('uk-margin-small');
    $('.dataTables_filter input').addClass('uk-input uk-form-width-medium');
    $('.dataTables_filter').addClass('uk-margin-small');
    table.buttons().container().removeClass('dt-buttons').addClass('uk-button-group');
}


// TODO: Add a right-click context menu for <li> tagged rows
function attachContextMenu(selector, menuItems) {
    const contextMenu = $('<div id="contextMenu" class="uk-context-menu"></div>');
    const menuList = $('<ul class="context-menu-items"></ul>');
    menuItems.forEach(item => {
        const menuItem = $(`<li>${item.text}</li>`);
        menuItem.on('click', function() {
            item.action();
            contextMenu.hide();
        });
        menuList.append(menuItem);
    });
    contextMenu.append(menuList);
    $('body').append(contextMenu);

    $(selector).on('contextmenu', function(e) {
        e.preventDefault();
        $('.uk-context-menu').hide();
        contextMenu.css({
            display: 'block',
            left: e.pageX + 'px',
            top: e.pageY + 'px'
        });
    });

    $(document).click(function(e) {
        contextMenu.hide();
    });
}

window.setupFormSubmission = function(formId, url) {
    const form = document.getElementById(formId);
    if (!form) {
        console.error('Form with ID "' + formId + '" not found.');
        return;
    }

    form.addEventListener("submit", function(e) {
        e.preventDefault();

        const csrfToken = getCsrfCookie();
        const method = this.getAttribute('data-method') || this.method;
        const isGetRequest = method.toUpperCase() === 'GET';

        // Build the JSON data object
        const jsonData = {};

        // Collect regular form fields
        const formData = new FormData(this);
        for (const [key, value] of formData.entries()) {
            if (key !== 'data') {  // Exclude the 'data' key from regular fields
                jsonData[key] = value;
            }
        }

        // Collect the dynamically generated fields under the 'data' key
        const categoryFields = form.querySelector('#category-fields');
        if (categoryFields) {
            jsonData.data = {};
            categoryFields.querySelectorAll('input, textarea').forEach(field => {
                jsonData.data[field.name] = field.value;
            });
        }

        // Create the request options
        const requestOptions = {
            method: method,
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrfToken,
            },
        };

        // Include the request body only for non-GET/HEAD requests
        if (!isGetRequest) {
            requestOptions.body = JSON.stringify(jsonData);
        }

        // Use the provided URL if available, otherwise use the form's action attribute
        const submissionUrl = url || this.action;

        // Construct the URL for GET requests
        const finalUrl = isGetRequest ? `${submissionUrl}?${new URLSearchParams(jsonData)}` : submissionUrl;

        fetch(finalUrl, requestOptions)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log(data);
            // If the URL is for creating an invitation, display the invitation link
            if (url === "/admin/invitations") {
                alert("Invitation created:\n\n " + data.invite_link);
            } else if (url === "/admin/register") {
                alert("Registration successful! You will be redirected to the login page.");
                window.location.href = "/login";
            } else {
                location.reload();
            }
        })
        .catch(error => {
            console.error('There was a problem with your form fetch operation:', error);
        });
    });
}