$(document).ready(function() {
    var clientId = $(".uk-container").data("client-id");
    var csrfToken = getCsrfCookie();

    function initClientDetailsEditing() {
        var editableFields = $("#client-email, #client-phone");
        var editClientDetailsBtn = $("#edit-client-details");

        function toggleEditState(isEditable) {
            editableFields.attr("contenteditable", isEditable);
            editClientDetailsBtn.text(isEditable ? "Cancel Edit" : "Edit Client Details");
        }

        editClientDetailsBtn.click(function() {
            var isCurrentlyEditable = editableFields.first().attr("contenteditable") === "true";
            toggleEditState(!isCurrentlyEditable);

            if (!isCurrentlyEditable) {
                if ($(".save-client-btn").length === 0) {
                    var saveClientBtn = $('<button class="save-client-btn uk-button uk-button-default uk-margin-small-left">Save Changes</button>');
                    editClientDetailsBtn.after(saveClientBtn);

                    saveClientBtn.click(function() {
                        var clientChanges = {};

                        editableFields.each(function() {
                            var $this = $(this);
                            $this.removeAttr("contenteditable");

                            var fieldName = $this.attr("id").replace("client-", "");
                            var fieldValue = $this.text().trim();

                            clientChanges[fieldName] = fieldValue;
                        });

                        if (!$.isEmptyObject(clientChanges)) {
                            sendPatchRequest('/clients/' + clientId, clientChanges);
                        }

                        $(this).remove();
                        toggleEditState(false);
                    });
                }
            } else {
                $(".save-client-btn").remove();
            }
        });
    }

    // Function to send PATCH request
    function sendPatchRequest(url, data, callback) {
        $.ajax({
            url: url,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify(data),
            headers: { 'X-CSRF-TOKEN': csrfToken },
            success: function(response) {
                console.log('Success:', response.message);
                if (callback) {
                    callback();
                }
            },
            error: function(error) {
                console.log('Error:', error);
            }
        });
    }

    // Initialize client details editing
    initClientDetailsEditing();
});