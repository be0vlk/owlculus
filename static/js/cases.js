// Client-side stuff is really not my strong suit so, this would be a great place to start contributing to the project!
// Seriously, help.
// Please?

$(document).ready(function(){
    var caseId = $(".uk-container").data("case-id");
    var csrfToken = getCsrfCookie();
    var clientId = $(".uk-container").data("client-id");

    // Dynamically generate note category buttons and load category fields
    function generateNoteCategoryButtons() {
        var caseType = $(".uk-container").data("case-type").toLowerCase();
        var categoriesPath = '/static/note_categories.json';

        if (caseType === 'person') {
            categoriesPath = '/static/person_notes.json';
        } else if (caseType === 'company') {
            categoriesPath = '/static/company_notes.json';
        }

        $.getJSON(categoriesPath, function(categories) {
            var buttonGroup = $('.uk-button-group');
            Object.keys(categories).forEach(function(category) {
                var button = $('<button class="uk-button uk-button-default note-category" data-category="' + category + '">' + category + '</button>');
                buttonGroup.prepend(button);
            });

            $('.note-category').first().trigger('click');
        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.log('Failed to load note categories: ', textStatus, errorThrown);
        });
    }

    // Function to handle case details editing
    function initCaseDetailsEditing() {
        var editableParagraphs = $("p:not(:contains('Created'))");
        var editCaseDetailsBtn = $("#edit-case-details");

        function toggleEditState(isEditable) {
            editableParagraphs.attr("contenteditable", isEditable);
            editCaseDetailsBtn.text(isEditable ? "Cancel Edit" : "Edit Case Details");
        }

        editCaseDetailsBtn.click(function(){
            var isCurrentlyEditable = editableParagraphs.first().attr("contenteditable") === "true";
            toggleEditState(!isCurrentlyEditable);

            if (!isCurrentlyEditable) {
                if ($(".save-all-btn").length === 0) {
                    var saveAllBtn = $('<button class="save-all-btn uk-button uk-button-default uk-margin-small-left">Save All Changes</button>');
                    editCaseDetailsBtn.after(saveAllBtn);

                    saveAllBtn.click(function() {
                        var caseChanges = {};
                        var clientChanges = {};

                        editableParagraphs.each(function() {
                            var $this = $(this);
                            $this.removeAttr("contenteditable");

                            var label = $this.find('strong').text().slice(0, -1).toLowerCase().replace(' ', '_');
                            var fieldValue = $this.text().slice($this.find('strong').text().length).trim();

                            if (label.includes("client_")) {
                                var fieldName = label.replace('client_', '');
                                clientChanges[fieldName] = fieldValue;
                            } else {
                                caseChanges[label] = fieldValue;
                            }
                        });

                        if (!$.isEmptyObject(caseChanges)) {
                            sendPatchRequest('/cases/' + caseId, caseChanges);
                        }
                        if (!$.isEmptyObject(clientChanges)) {
                            sendPatchRequest('/clients/' + clientId, clientChanges);
                        }

                        $(this).remove();
                        toggleEditState(false);
                    });
                }
            } else {
                $(".save-all-btn").remove();
            }
        });
    }

    // Client-side function to handle case deletion (see api.cases for server-side code)
    function initCaseDeletion() {
        $("#delete-case").click(function() {
            if (confirm('Are you sure you want to delete this case?')) {
                $.ajax({
                    url: '/cases/' + caseId,
                    type: 'DELETE',
                    headers: { 'X-CSRF-TOKEN': csrfToken },
                    success: function() {
                        alert('Case deleted successfully.');
                        window.location.href = '/';
                    },
                    error: function(error) {
                        console.log('Error deleting case:', error);
                        alert('Error deleting case. Please try again.');
                    }
                });
            }
        });
    }

    // File upload form submission
    $('#evidence-upload-form').on('submit', function(e) {
        e.preventDefault();

        var formData = new FormData(this);

        $.ajax({
            url: '/cases/' + caseId + '/files',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: { 'X-CSRF-TOKEN': csrfToken },
            success: function(response) {
                alert('File uploaded successfully.');
                $('#evidence-upload-form')[0].reset();
                // Refresh the evidence list
                $("#show-evidence").trigger("click");
            },
            error: function(xhr) {
                alert('Error uploading file: ' + xhr.responseJSON.message);
            }
        });
    });


// Function to handle correlation requests
function initCorrelationRequest() {
    var correlationsBtn = $("#request-correlations");

    correlationsBtn.click(function() {
        var caseNumber = $(".uk-container").data("case-number");
        var requestData = {
            case_number: caseNumber,
            all_cases: false
        };

        $.ajax({
            url: '/tools/correlations',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(requestData),
            headers: { 'X-CSRF-TOKEN': csrfToken },
            success: function(response) {
                displayCorrelations(response);
            },
            error: function(error) {
                console.log('Error:', error);
            }
        });
    });
}

    function displayCorrelations(data) {
        console.log("Correlation Data:", data);

        var correlationResultsContent = $("#correlation-results-content");
        correlationResultsContent.empty();

        if ($.isEmptyObject(data)) {
            correlationResultsContent.append('<p>No correlations found.</p>');
        } else {
            var correlationsContainer = $('<div class="uk-height-large uk-overflow-auto"></div>');
            var correlationsList = $('<ul class="uk-list uk-list-divider"></ul>');

            var groupedCorrelations = {};

            $.each(data, function(caseNumber, correlations) {
                $.each(correlations, function(matchedCaseNumber, matchedCorrelations) {
                    if (!groupedCorrelations[matchedCaseNumber]) {
                        groupedCorrelations[matchedCaseNumber] = [];
                    }
                    groupedCorrelations[matchedCaseNumber] = groupedCorrelations[matchedCaseNumber].concat(matchedCorrelations);
                });
            });

            $.each(groupedCorrelations, function(matchedCaseNumber, matchedCorrelations) {
                var caseItem = $('<li></li>');
                caseItem.append('<h3>Case ' + matchedCaseNumber + '</h3>');

                var correlationDetails = $('<ul class="uk-list uk-margin-left"></ul>');

                matchedCorrelations.forEach(function(correlation) {
                    var correlationItem = $('<li></li>');
                    correlationItem.append('<strong>Category:</strong> ' + correlation.category + '<br>');
                    correlationItem.append('<strong>Key:</strong> ' + correlation.key + '<br>');
                    correlationItem.append('<strong>Value:</strong> ' + correlation.value + '<br>');
                    correlationDetails.append(correlationItem);
                });

                caseItem.append(correlationDetails);
                correlationsList.append(caseItem);
            });

            correlationsContainer.append(correlationsList);
            correlationResultsContent.append(correlationsContainer);
        }

        UIkit.modal("#correlation-results-modal").show();
    }

    // Function to send PATCH request that's reused elsewhere
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

    // Show Evidence button click event
    $("#show-evidence").click(function() {
        $.ajax({
            url: '/cases/' + caseId + '/files',
            type: 'GET',
            success: function(response) {
                if (response && response.files) {
                    displayEvidence(response.files);
                } else {
                    console.log('Invalid response data:', response);
                }
            },
            error: function(error) {
                console.log('Error:', error);
            }
        });
    });


function displayEvidence(files) {
    var evidenceList = $("#evidence-list");
    evidenceList.empty();

    if (files.length === 0) {
        evidenceList.append('<li>No evidence files found.</li>');
    } else {
        var fileTree = {};

        // Build the file tree structure
        files.forEach(function(file) {
            var parts = file.split('/');
            var currentLevel = fileTree;

            parts.forEach(function(part, index) {
                if (index === parts.length - 1) {
                    currentLevel[part] = file;
                } else {
                    if (!currentLevel[part]) {
                        currentLevel[part] = {};
                    }
                    currentLevel = currentLevel[part];
                }
            });
        });

        // Recursively render the file tree
        function renderFileTree(tree, parentElement) {
            Object.keys(tree).forEach(function(key) {
                var value = tree[key];

                if (typeof value === 'string') {
                    // Leaf node (file)
                    var fileDownloadUrl = '/cases/' + caseId + '/files?filename=' + encodeURIComponent(value);
                    var fileLink = $('<a></a>')
                        .attr('href', fileDownloadUrl)
                        .attr('download', key)
                        .text(key);
                    var fileItem = $('<li></li>').append(fileLink);
                    parentElement.append(fileItem);
                } else {
                    // Directory node
                    var directoryItem = $('<li></li>');
                    var directoryName = $('<span></span>').text(key);
                    var subList = $('<ul></ul>');

                    directoryItem.append(directoryName);
                    renderFileTree(value, subList);
                    directoryItem.append(subList);
                    parentElement.append(directoryItem);
                }
            });
        }

        renderFileTree(fileTree, evidenceList);
    }

    UIkit.modal('#evidence-modal').show();
}


    generateNoteCategoryButtons();

    // Function to load category fields based on selected category
    function loadCategoryFields() {
        $('#category').on('change', function() {
            var selectedCategory = $(this).val();

            if (selectedCategory) {
                $.getJSON('/static/note_categories.json', function(data) {
                    var categoryFields = data[selectedCategory];
                    var fieldsHtml = '';

                    if (categoryFields) {
                        categoryFields.forEach(function(field) {
                            fieldsHtml += '<div class="uk-margin">';
                            fieldsHtml += '<label class="uk-form-label" for="' + field.name + '">' + field.label + '</label>';
                            fieldsHtml += '<div class="uk-form-controls">';

                            if (field.type === 'text') {
                                fieldsHtml += '<input class="uk-input" type="text" id="' + field.name + '" name="' + field.name + '" placeholder="' + (field.placeholder || '') + '">';
                            } else if (field.type === 'textarea') {
                                fieldsHtml += '<textarea class="uk-textarea" id="' + field.name + '" name="' + field.name + '" rows="5" placeholder="' + (field.placeholder || '') + '"></textarea>';
                            } else if (field.type === 'richtext') {
                                fieldsHtml += '<div id="' + field.name + '-editor"></div>';
                            }

                            fieldsHtml += '</div>';
                            fieldsHtml += '</div>';
                        });
                    } else {
                        fieldsHtml = '<p>No fields defined for the selected category.</p>';
                    }

                    $('#category-fields').html(fieldsHtml);

                    // Initialize Quill editors for richtext fields
                    categoryFields.forEach(function(field) {
                        if (field.type === 'richtext') {
                            new Quill('#' + field.name + '-editor', {
                                theme: 'snow'
                            });
                        }
                    });
                }).fail(function() {
                    alert('Failed to load category fields. Please try again.');
                });
            } else {
                $('#category-fields').empty();
            }
        });
    }

    // Function to fetch and display notes for a specific category
    function displayNotesForCategory(category) {
        console.log('Fetching notes for category:', category);
        $.getJSON('/cases/' + caseId + '/notes', function(notes) {
            console.log('Notes fetched:', notes);
            var notesContainer = $('#notes-container');
            notesContainer.empty();

            var categoryNotes = notes.filter(function(note) {
                console.log('Note category:', note.category, 'Filter category:', category);
                return note.category === category;
            });

            if (categoryNotes.length > 0) {
                categoryNotes.forEach(function(note) {
                    var noteHtml = '<div class="uk-card uk-card-default uk-card-body uk-margin-bottom">';
                    noteHtml += '<h4>' + note.category + '</h4>';
                    if (note.data) {
                        $.each(note.data, function(key, value) {
                            if (key === 'Notes') {
                                // Render the Quill editor content as HTML
                                noteHtml += '<div class="note-content">' + value + '</div>';
                            } else {
                                noteHtml += '<p><strong>' + key + ':</strong> ' + value + '</p>';
                            }
                        });
                    }
                    noteHtml += '<button class="uk-button uk-button-primary edit-note" data-note-id="' + note.id + '">Edit</button>';
                    noteHtml += '</div>';
                    notesContainer.append(noteHtml);
                });
            } else {
                notesContainer.html('<p>No notes found for this category.</p>');
            }
        }).fail(function(jqXHR, textStatus, errorThrown) {
            alert('Failed to fetch notes: ' + textStatus + ' - ' + errorThrown);
        });
    }

    // Event delegation for note category buttons
    $(document).on('click', '.note-category', function() {
        var category = $(this).data('category');
        if(category) {
            displayNotesForCategory(category);
        } else {
            console.log('Category data is undefined for this button.', $(this).text());
        }
    });

    // Edit Note Modal handling
    $(document).on('click', '.edit-note', function() {
        var noteId = $(this).data('note-id');
        var category = $(this).data('category');

        // Fetch note details and prefill the form for editing
        $.getJSON('/cases/' + caseId + '/notes/' + noteId, function(note) {
            var noteFields = $('#note-fields');
            noteFields.empty();

            $.each(note.data, function(key, value) {
                var fieldHtml = '<div class="uk-margin">';
                fieldHtml += '<label class="uk-form-label" for="' + key + '">' + key + '</label>';
                fieldHtml += '<div class="uk-form-controls">';
                fieldHtml += '<input class="uk-input" type="text" id="' + key + '" name="' + key + '" value="' + value + '">';
                fieldHtml += '</div>';
                fieldHtml += '</div>';
                noteFields.append(fieldHtml);
            });

            // Set the form's data-note-id attribute
            $('#noteForm').attr('data-note-id', noteId);
            UIkit.modal("#edit-note-modal").show();
        });
    });

    function initRichTextEditors() {
        $('.richtext-editor').each(function() {
            var editorId = $(this).attr('id');
            var editor = new Quill('#' + editorId, {
                theme: 'snow'
            });
            // Store the Quill editor instance in the jQuery data for the element
            $('#' + editorId).data('quill', editor);
        });
    }

    $('#noteForm').on('submit', function(e) {
        e.preventDefault();

        var noteId = $(this).attr('data-note-id');
        var formData = $(this).serializeArray();
        var updatedData = {};

        // Convert form data to an object
        $.each(formData, function(_, field) {
            if (field.name === 'Other Notes') {
                // Retrieve the Quill editor for the "Other Notes" field from the jQuery data
                var editor = $('#OtherNotes-editor').data('quill');
                var editorContent = editor.root.innerHTML;
                updatedData[field.name] = editorContent;
            } else {
                // Use the regular field value for other fields
                updatedData[field.name] = field.value;
            }
        });

        // Use the existing sendPatchRequest function
        var category = $('.note-category.uk-active').data('category');
        sendPatchRequest('/cases/' + caseId + '/notes/' + noteId, { category: category, data: updatedData }, function() {
            UIkit.modal("#edit-note-modal").hide();
            // Refresh the notes display
            displayNotesForCategory(category);
        });
    });

    // Function to handle report generation
    function initReportGeneration() {
        var generateReportBtn = $("#generate-report");

        generateReportBtn.click(function() {
            $.ajax({
                url: '/cases/' + caseId + '/report',
                type: 'GET',
                headers: { 'X-CSRF-TOKEN': csrfToken },
                success: function(response) {
                    alert('Report generated successfully.');
                },
                error: function(error) {
                    console.log('Error generating report:', error);
                    alert('Error generating report. Please try again.');
                }
            });
        });
    }

    // Initialize things
    initCaseDetailsEditing();
    initCaseDeletion();
    initCorrelationRequest();
    loadCategoryFields();
    initRichTextEditors();
    initReportGeneration();

    // Load notes for the first category by default if available
    var firstCategory = $('.note-category').first().data('category');
    if(firstCategory) {
        displayNotesForCategory(firstCategory);
    } else {
        console.log('No category data available for the first note category button.');
    }
});



setupFormSubmission("noteForm");