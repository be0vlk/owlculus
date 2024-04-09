# Owlculus: OSINT Toolkit

<p align="center">
  <img src="https://i.imgur.com/Cuf4hMK.png" />
</p>

Owlculus is purpose built for managing OSINT investigation cases. Based on my old and now archived pyqt project of the same name, this version comes with significantly enhanced capabilties and extensibility.

**NOTE:** This project is now and will always be 100% free and open-source, no matter how much it improves. If you're feeling generous, donate to your favorite charity instead :)

## Features
- Create and track cases with customizable report number formats.
- A separate client database table to manage client contact information.
- Web-based multi-user collaboration with predefined, customizable roles for different permissions.
- The backend RESTful API architecture enables various types of automation and integration.
- Run popular CLI-based OSINT tools like holehe and maigret right in the app.
- Automatically scan for correlations between cases. Investigated John Doe two months ago in a different case? The scan will find it.
- Meet Strixy, your ChatGPT assistant with file upload functionality to help you with analysis tasks.

## Roadmap
I will be very actively maintaining and improving this application and am always open to suggestions. If you have any of those, or come across any bugs, please feel free to open an issue right here on GitHub. Some things definitely planned are:

- Enhanced client-side code and user interface
- More custom built and open-source tool compatibility
- Different ways to add evidence to case files (browser extension?)
- Better, more powerful ChatGPT integration
- Docker containerization

## Installation
I highly recommend installing this on Linux (specifically tested on Debian 11 and Ubuntu 22.04), although not strictly required. I've included some automation scripts to make setup easier. You MUST follow each of these steps for the app to install and work properly. Run all of the following commands from the project root folder:

1. `cat .env.example > .env` After you do this, make sure to edit the values in ".env" to suit your use, especially "UPLOAD_FOLDER", "DATABASE_URI" and, if you plan to use ChatGPT integration, "OPENAI_API_KEY".
2. `pip3 install -r requirements.txt`
3. `chmod +x db_setup.sh && ./db_setup.sh`
4. `python3 app.py`

See, wasn't that easy? The setup script also generates the default admin user and prints the credentials to the console.

**IMPORTANT:** Make sure to save the password somewhere safe or you won't be able to login! The password is encrypted in the PostgreSQL database so you can't just copy it from there. Worst case scenario, if you miss this part, you have to drop the owlculus db and user, delete the migrations folder, and run "db_setup.sh" again.

## Usage
### Case Dashboard
![Imgur](https://i.imgur.com/77ndGNj.png)
After logging in as the admin user, you'll be redirected to the main case dashboard where you can create your first case by clicking the aptly named "Create Case" button. A modal will pop up asking for basic case details. Optionally, before you create the case, click "Clients" in the sidebar to add a client which you will then be able to add the case to.

The "Add User to Case" button allows you to assign other users to the case, allowing them to access it. By default, non-admin users cannot interact with any cases they are not assigned to. You can also sort the table by any column, search for cases in the search bar, or export the list to CSV.

Now, double-click directly on the case in the table and you'll be redirected to that case's detail page.

### Case Detail
This page displays the basic case information and allows you to create and view notes, upload/download evidence to the case folder, run correlation scans, and delete the case. Simply click whichever note category you want to edit (by the way these are based on the JSON templates in "/static") and save the notes. They will now be displayed whenever you view the case page. Now, let's talk about some of the less obvious buttons.

`Generate Report` Creates both HTML and PDF reports, which really are just the case notes and basic details, and saves them in the cases folder on disk where they can be downloaded via the "Show Evidence" as explained below.

`Find Correlations` Scans the evidence associated with other cases in the database and informs you of any matches. For now, this scans the notes and filenames of files in the cases directory on disk but will definitely be expanded in the future. So for example, if you added the phone number "123-456-7890" in an old case, then run the correlation scan on a new one that also has the same number in its notes, you'll get a hit. In the screenshot, I ran the tool from case "2404-02" and you can see the matches in "2404-01".

![Imgur](https://i.imgur.com/F4JEcqk.png)

`Show Evidence` Displays a modal with a file tree showing the files that are present in the case folder. Click the file to download it to your local system. You can also upload new files here. It's important to note that uploads are restricted to allowlisted extensions that are set in "utils.helpers".

### Tools
This page allows you to conveniently run CLI-based OSINT tools right from the app. It both outputs the results in real time to the browser as well as saves the results to a txt file in the given case's folder on disk where it can downloaded, as explained above. There's limited support at the moment but this is a huge area of the roadmap, I promise! For now, you can also expand the functionality yourself in the "api.tools.tool_runner" module and its associated "/templates/tools/tools.html" frontend.

Note that these tools run asyncrhonously so feel free to run a couple at once.

`Holehe` The popular email/account enumeration tool by [megadose](https://github.com/megadose/holehe).

`Maigret` Username enumeration tool by [soxoj](https://github.com/soxoj/maigret).

`Redd Baron` A custom tool by yours truly that enumerates the given user's Reddit post and comment history.

`Strixy` Your ChatGPT assistant, prompted to function as an OSINT analyst. This is still a WIP but the basic functionality is there. Try doing things like uploading the results of the Redd Baron tool and asking it something like "analyze this user's posting patterns and suggest my next investigative step". You can completely customize the assistant in "utils.app_setup", but you need to do this before the first run. Otherwise, you'll have to login to your OpenAI playground and adjust it there.

### Admin
Basic admin portal that allows you to create and delete users. The dropdown menu allows you to assign a role to the user. 

`Admin` Full access to do anything in the app, including run all tools, view and edit any case/client, etc.

`Investigator` Standard read/write access to any cases they have been assigned to. This includes editing notes and running the various tools offered in app. By default they cannot create cases.

`Analyst` Essentially, read-only access. They can review notes and download evidence from any case they are assigned to, but by default have no access to CLI tools.
