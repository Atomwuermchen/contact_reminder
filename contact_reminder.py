# IMPORTS
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
import telegram
import sqlite3
import datetime
import pytz
import python_config
import os

# load configuration
# CONF_NAME = "example_config.conf"
CONF_NAME = "contact_reminder.conf"
conf = python_config.load(os.path.join(os.path.dirname(os.path.realpath(__file__)), CONF_NAME))
# global variable definition
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),conf["db_filename"])
TIMEZONE = conf["timezone"]
TOKEN = conf["bot_token"]
# global variable definition
FIRST_NAME, LAST_NAME, INTERVAL, LAST_CONTACT = range(4)
REMINDER_TIME = 0
sql_dict = {}
jobs = {}


# DATABASE FUNCTION DEFINITIONS
def connect_database(db_path):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_path: database path
    :return: Connection object
    """
    try:
        db = sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print("Error")
        print(e)
        return
    return db


def create_tables(db):
    """ create the tables recipes and meals in the database
        in case they don't already exist
    :param db: connection object
    :return: None
    """
    sql_create_user_table = """ CREATE TABLE IF NOT EXISTS users (
                                        user_id integer PRIMARY KEY,
                                        chat_id integer NOT NULL,
                                        is_active integer NOT NULL,
                                        reminder_time TEXT NOT NULL
                                        ); """
    sql_create_contact_table = """ CREATE TABLE IF NOT EXISTS contacts (
                                    contact_id integer PRIMARY KEY,
                                    first_name text NOT NULL,
                                    last_name text,
                                    interval integer NOT NULL,
                                    last_contact text,
                                    user_id integer NOT NULL,
                                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                                    UNIQUE (first_name, last_name, user_id)
                                    ); """

    try:
        cur = db.cursor()
        cur.execute(sql_create_user_table)
        cur.execute(sql_create_contact_table)
    except sqlite3.Error as e:
        print("Error")
        print(e)


# helper function to check if a user is a registered user in the users table
def is_registered(db_path, chat_id):
    db = connect_database(db_path)
    sql = ''' SELECT user_id FROM users WHERE chat_id = ?'''
    try:
        cur = db.cursor()
        cur.execute(sql, (chat_id,))
        is_registered_user = True if cur.fetchone() is not None else False
        db.close()
        return is_registered_user
    except sqlite3.Error as e:
        print(e)
        db.close()
        return None


# CHATBOT FUNCTION DEFINITIONS, HANDLERS AND DISPATCHER
# start command
def start(update, context):
    # query database for chat id to determine which message to send
    global DB_PATH
    is_registered_user = is_registered(DB_PATH, update.effective_chat.id)
    if is_registered_user is True:
        msg = "Welcome back. You are a registered user of my stay-in-touch reminder service.\n" \
              "You can type /help in order to find out by which commands you can interact with me."
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
    elif is_registered_user is False:
        msg = "Welcome! I am the stay-in-touch bot. I can help you remember with whom you want to stay in" \
              "contact by sending you daily reminders for reaching out to a list of people which you" \
              "can freely define. You can also specify how often you want to contact each individual person.\n" \
              "Sounds good? I need to register your chat_id in order to get started.\n" \
              "Please also be aware that all the (personal) information such as contact names will be" \
              "stored without encryption in my database. So use at your own risk. I cannot take any" \
              "responsibility for your actions.\n" \
              "So, do you want to become an active user?"
        custom_keyboard = [['Please register me!'], ['No, thank you!']]
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                                 reply_markup=telegram.ReplyKeyboardMarkup(custom_keyboard,
                                                                           one_time_keyboard=True))
    else:
        msg = "Sorry. An error occurred. Please try again later."
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())


# start command
def help(update, context):
    msg = "Hi there. I can remind you automatically every day to stay in touch with your friends and relatives." \
          "You can send me the following commands.\n" \
          "/register - Registers your ID as an active user.\n" \
          "/newcontact - Registers a new contact\n" \
          "/editcontact - Edits information for one of your contacts\n" \
          "/printcontacts - Prints a list of all of your current contacts\n" \
          "/activate - (Re)Activates the reminder. Afterwards you will get a reminder every day\n" \
          "/deactivate - Deactives daily reminders for your chat ID\n" \
          "/time - Allows to set a new daily reminder time\n" \
          "/remindme - Immediately sends the due contacts reminder\n"
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg)


# activate command to set the is_active flag for a user to true/1
def activate(update, context):
    # determine if user is registered and set is_active to 1
    global DB_PATH
    if is_registered(DB_PATH, update.effective_chat.id):
        # update database
        sql = ''' UPDATE users SET is_active = ? WHERE chat_id = ?'''
        db = connect_database(DB_PATH)
        cur = db.cursor()
        cur.execute(sql, (1, update.effective_chat.id))
        db.commit()
        # update the job
        # retrieve all jobs having the chat_id as name
        current_jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
        # current_jobs is a tuple which should ideally only have one item. Enable it
        for job in current_jobs:
            job.enabled = True
        # query reminder time value for reply message to user
        sql = ''' SELECT reminder_time FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        reminder_time = cur.fetchone()[0]
        msg = "Daily reminders at {} have been activated. To deactivate them use " \
              "the /deactivate command".format(reminder_time)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
    else:  # if user is not registered, send back error message
        msg = "You are not a registered user. Please register first using the /register command"
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())


# deactivate command to set the is_active flag for a user to false/0
def deactivate(update, context):
    # determine if user is registered and set is_active to 1
    global DB_PATH
    if is_registered(DB_PATH, update.effective_chat.id):
        # update database
        sql = ''' UPDATE users SET is_active = ? WHERE chat_id = ?'''
        db = connect_database(DB_PATH)
        cur = db.cursor()
        cur.execute(sql, (0, update.effective_chat.id))
        db.commit()
        # retrieve all jobs having the chat_id as name
        current_jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
        # current_jobs is a tuple which should ideally only have one item. Disable it
        for job in current_jobs:
            job.enabled = False
        # query reminder time value for reply message to user
        sql = ''' SELECT reminder_time FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        reminder_time = cur.fetchone()[0]
        msg = "Daily reminders at {} have been deactivated. To activate them use " \
              "the /activate command".format(reminder_time)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
    else:  # if user is not registered, send back error message
        msg = "You are not a registered user. Please register first using the /register command"
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())


# define a cancel function which will be the fallback option for all conversations to follow
def cancel(update, context) -> int:
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="It seems as if you do not want to continue executing your previous command.\n"
                                  "I will keep listening to you nevertheless.",
                             reply_markup=telegram.ReplyKeyboardRemove())
    return ConversationHandler.END


# register user conversation
def register(update, context) -> int:
    # query database for chat id to see if chat_id is registered already
    chat_id = update.effective_chat.id
    global DB_PATH
    db = connect_database(DB_PATH)
    sql = ''' SELECT user_id FROM users WHERE chat_id = ?'''
    try:
        cur = db.cursor()
        cur.execute(sql, (chat_id,))
        is_registered_user = True if cur.fetchone() is not None else False
    except sqlite3.Error as e:
        print(e)
        return ConversationHandler.END
    db.close()
    # if user is registered already, user cannot be registered again
    if is_registered_user:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='You are already a registered user. If you want to activate or deactivate '
                                      'your reminder settings, please use the /activate and /deactivate command.',
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return ConversationHandler.END
    # otherwise start the registration converation.
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Cool! Then I will register our mutual '
                                    'chat ID in my database and set you as an '
                                    'active user. At what time each day '
                                    'would you like to be reminded of your '
                                    'due contacts? Please answer in HH:MM:SS format.',
                                 reply_markup=telegram.ReplyKeyboardRemove())
        # REMINDER_TIME = 0
        return 0


def reminder_time(update, context) -> int:
    # try converting user-supplied time into datetime object to see if correct format was used
    try:
        reminder_datetime = datetime.datetime.strptime(update.message.text, '%H:%M:%S')
    except ValueError:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Hmm that didn't work unfortunately. Are you sure wrote desired reminder "
                                      "time in the HH:MM:SS format? So in 24 hour format I mean. Let's give "
                                      "it another try.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
        # REMINDER_TIME = 0
        return 0
    # if conversion was successful, we have all necessary data to add the user with his chat_id to
    # the users table
    sql = '''INSERT INTO users (chat_id, is_active, reminder_time) VALUES (?,?,?)'''
    try:
        global DB_PATH
        db = connect_database(DB_PATH)
        cur = db.cursor()
        cur.execute(sql, (update.effective_chat.id, 1, update.message.text))
        db.commit()
        db.close()
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Something went wrong. I could not add you to the database. Please "
                                      "try again.",
                                 reply_markup=telegram.ReplyKeyboardRemove())

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Ok, that is all I need for now. I added you to the database. You can always '
                                  'type /help to find out which commands you can use to interact with me.',
                             reply_markup=telegram.ReplyKeyboardRemove())
    return ConversationHandler.END


# edit reminder time conversation
def edit_reminder_time_start(update, context) -> int:
    global DB_PATH
    if is_registered(DB_PATH, update.effective_chat.id):
        msg = "Sure, let's update your reminder time. Things in life can change. Please tell me your new " \
              "desired reminder time in HH:MM:SS format."
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return 0
    else:
        msg = "You are not a registered user. Please register first using the /register command"
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return ConversationHandler.END


def edit_reminder_time_end(update, context) -> int:
    # try converting user-supplied time into datetime object to see if correct format was used
    try:
        reminder_datetime = datetime.datetime.strptime(update.message.text, '%H:%M:%S')
    except ValueError:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Hmm that didn't work unfortunately. Are you sure wrote desired reminder "
                                      "time in the HH:MM:SS format? So in 24 hour format I mean. Let's give "
                                      "it another try.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return 0
    # if converting was successful, we can update the database
    sql = ''' UPDATE users SET reminder_time= ? WHERE chat_id = ?'''
    global DB_PATH
    db = connect_database(DB_PATH)
    cur = db.cursor()
    cur.execute(sql, (update.message.text, update.effective_chat.id))
    db.commit()
    db.close()
    global jobs
    global TIMEZONE
    reminder_datetime_tz = reminder_datetime.time().replace(tzinfo=pytz.timezone(TIMEZONE))
    jobs[update.effective_chat.id] = context.job_queue.run_daily(reminder, time=reminder_datetime_tz,
                                                                 context=update.effective_chat.id,
                                                                 name=str(update.effective_chat.id))
    # we also need to change the scheduled time in the job itself
    msg = "Done! From now on you will receive reminders at {}".format(update.message.text)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg,
                             reply_markup=telegram.ReplyKeyboardRemove())
    return ConversationHandler.END


# new contact conversation
def new_contact(update, context) -> int:
    global DB_PATH
    if not is_registered(DB_PATH, update.effective_chat.id):
        msg = "You are not a registered user. Please register first using the /register command"
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return ConversationHandler.END
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Ok. Let's add a new contact to your reminder database.\n"
                                  "What is his or her first name?",
                             reply_markup=telegram.ReplyKeyboardRemove())
    # FIRST_NAME = 0
    return 0


def first_name(update, context) -> int:
    global sql_dict
    first_name = update.message.text
    sql_dict["first_name"] = first_name.strip()
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="So we will add {}.\n"
                                  "Does he or she also have a last name? If so, please tell it to me. "
                                  "If you do not wish to add a last name please send the /skip command"
                             .format(first_name),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # LAST_NAME = 1
    return 1


def last_name(update, context) -> int:
    global sql_dict
    last_name = update.message.text
    sql_dict["last_name"] = last_name.strip()
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Perfect. Your contacts name is {} {}.\n"
                                  "How often per year do you want to get in touch with him or her?"
                             .format(sql_dict["first_name"], sql_dict["last_name"]),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # INTERVAL = 2
    return 2


def skip_last_name(update, context) -> int:
    global sql_dict
    sql_dict["last_name"] = ""
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Ok, let's skip the last name and just call your contact {}.\n"
                                  "How often per year do you want to get in touch with him or her?"
                             .format(sql_dict["first_name"]),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # INTERVAL = 2
    return 2


def interval(update, context) -> int:
    global sql_dict, DB_PATH
    try:
        interval = int(365 / int(update.message.text))
    except Exception as ex:
        print(ex)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="You entered {}. But I asked you how often per year you want to get in "
                                      "touch with your contact. You have to enter a number. Let's try "
                                      "it again. How often per year do you want to get in touch with "
                                      "him or her.".format(update.effective_chat.id),
                                 reply_markup=telegram.ReplyKeyboardRemove())
        # INTERVAL = 2
        return 2
    sql_dict["interval"] = interval
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Got it. So you want to get in touch with {0} {1} roughly every {2} days.\n"
                                  "If you remember the date when you had contact with {0} {1} for the last "
                                  "time, please write it back in the format YYYY-MM-DD. If you respond anything "
                                  "else, I will simply assume that you want to get in touch with {0} {1} as "
                                  "soon as possible."
                             .format(sql_dict["first_name"], sql_dict["last_name"], sql_dict["interval"]),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # LAST_CONTACT = 3
    return 3



def last_contact(update, context) -> int:
    global sql_dict
    # try converting user input to datetime object
    try:
        last_contact_datetime = datetime.datetime.strptime(update.message.text, "%Y-%m-%d")
    # if not successful set last_contact_datetime such that a reminder will be due today
    except ValueError as e:
        last_contact_datetime = datetime.datetime.now() - datetime.timedelta(days=sql_dict["interval"])
    # set value in dictionary
    sql_dict["last_contact"] = last_contact_datetime.strftime('%Y_%m_%d')
    try:
        db = connect_database(DB_PATH)
        cur = db.cursor()
        sql = ''' SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You don't seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return
        else:
            sql_dict["user_id"] = result[0]
        # check if a row with this contact name already exists
        sql = '''SELECT contact_id FROM contacts WHERE first_name = ? AND last_name = ? AND user_id = ?'''
        cur.execute(sql, (sql_dict["first_name"], sql_dict["last_name"], sql_dict["last_name"]))
        query_result = cur.fetchall()
        # if the row already exists inform the user and do nothing more
        if len(query_result) > 0:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="A contact with name {} {} already exists for this user. You cannot "
                                          "add a contact more than once. Quitting ...",
                                     reply_markup=telegram.ReplyKeyboardRemove())
        # if the row does not exist, add it to the database and inform the user
        else:
            sql = '''INSERT INTO contacts (first_name, last_name, interval, last_contact, user_id) VALUES (?,?,?,?,?)'''
            sql_tuple = tuple(sql_dict.values())
            cur.execute(sql, sql_tuple)
            db.commit()
            db.close()

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Done. {} {} has been added to your contact list"
                                     .format(sql_dict["first_name"], sql_dict["last_name"]),
                                     reply_markup=telegram.ReplyKeyboardRemove())
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Something went wrong. I could not add your contact to the database. "
                                      "Please try again.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
    return ConversationHandler.END


# print contacts command
def print_contacts(update, context):
    global DB_PATH
    try:
        db = connect_database(DB_PATH)
        cur = db.cursor()
        sql = '''SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You don't seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return
        else:
            user_id = result[0]
        sql = ''' SELECT contact_id, first_name, last_name FROM contacts
        WHERE user_id = ?'''
        msg = ''
        for row in cur.execute(sql, (user_id,)):
            msg += "{}. {} {}\n".format(row[0], row[1], row[2])
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardRemove())
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Something went wrong. I could not add your contact to the database."
                                      "Please try again.",
                                 reply_markup=telegram.ReplyKeyboardRemove())


def reminder(context: telegram.ext.CallbackContext) -> None:
    # retrieve contacts of user
    # chat_id is passed as context of the job so it can be accessed as
    chat_id = context.job.context
    global DB_PATH
    due_contacts = []
    try:
        # get user_id which belongs to chat_id
        db = connect_database(DB_PATH)
        cur = db.cursor()
        sql = '''SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (chat_id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You don't seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return
        else:
            user_id = result[0]

        # get list of contacts with all data
        sql = '''SELECT first_name, last_name, interval, last_contact FROM
        contacts WHERE user_id = ?'''
        msg = "Hi there. Here is today's list of people who you want to stay in touch with:\n"
        ii = 1
        # determine for which contacts contacting is overdue
        for row in cur.execute(sql, (user_id,)):
            interval = row[2]
            last_contact = datetime.datetime.strptime(row[3], '%Y_%m_%d')
            if (last_contact + datetime.timedelta(days=interval)).date() <= datetime.date.today():
                # append contacts to due_contacts list and
                due_contacts.append(row[0] + ' ' + row[1])
                msg += "{}: {} {}\n".format(ii, row[0], row[1])
                ii += 1
        db.close()
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=chat_id,
                                 text="Oops. Something went wrong when retrieving your list of contacts.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return
    # check if there are due contacts and only send a reminder if that is the case
    if len(due_contacts) > 0:
        # send a message to the user with his due contacts and offer him a keyboard to mark users which have
        # been contacted
        custom_keyboard = [['I contacted ' + name + ' today!'] for name in due_contacts]
        custom_keyboard.append(["Nope, that's it for today"])
        context.bot.send_message(chat_id=chat_id,
                                 text=msg,
                                 reply_markup=telegram.ReplyKeyboardMarkup(custom_keyboard,
                                                                           one_time_keyboard=True))


# function to be called after a user has contacted a contact and send the
# "I contacted X Y today" via custom keyboard or in any other way
def last_contact_update(update, context):
    # The message is of the type "I contacted X Y" so we can split the message into its words and work only
    # with the last two
    splitted = update.message.text.split()
    first_name = splitted[-3]
    last_name = splitted[-2]

    # try to update the last_contact value of the contact in the contacts table
    global DB_PATH
    try:
        db = connect_database(DB_PATH)
        cur = db.cursor()
        # first get the user_id from the chat_id
        sql = '''SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You don't seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return
        else:
            user_id = result[0]
        # first determine if there is a first_name last_name record for that user_id in the contacts table
        sql = '''SELECT contact_id FROM contacts WHERE first_name = ? AND last_name = ? AND user_id = ?'''
        cur.execute(sql, (first_name, last_name, user_id))
        query_result = cur.fetchall()
        # if the record exists update the last_contact with todays date
        if len(query_result) > 0:
            sql = ''' UPDATE contacts SET last_contact = ? WHERE first_name = ? AND last_name = ? AND user_id = ?'''
            cur.execute(sql, (datetime.datetime.now().strftime("%Y_%m_%d"), first_name, last_name, user_id))
            db.commit()
            # get list of contacts with all data to construct new reply keyboard
            sql = '''SELECT first_name, last_name, interval, last_contact FROM
            contacts WHERE user_id = ?'''
            due_contacts = []
            # determine for which contacts contacting is overdue
            for row in cur.execute(sql, (user_id,)):
                interval = row[2]
                last_contact = datetime.datetime.strptime(row[3], '%Y_%m_%d')
                if (last_contact + datetime.timedelta(days=interval)).date() <= datetime.date.today():
                    # append contacts to due_contacts list and
                    due_contacts.append(row[0] + ' ' + row[1])
            # construct new keyboard
            custom_keyboard = [['I contacted ' + name + ' today!'] for name in due_contacts]
            custom_keyboard.append(["Nope, that's it for today"])
            # inform user about succesful database update and ask for further contacts
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Cool. You contacted {} {}. It's awesome that you stay in touch with people. "
                                          "I will let you know when you should contact him or her again. Is there "
                                          "anybody else whom you contacted today?".format(first_name, last_name),
                                     reply_markup=telegram.ReplyKeyboardMarkup(custom_keyboard,
                                                                               one_time_keyboard=True))
        # otherwise inform the user that the record does not exists
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Unfortunately, a contact with name {} {} does not exist in your database. "
                                          "This might be an indicator that your database is corrupt. Please get in "
                                          "touch with your admin".format(first_name, last_name),
                                     reply_markup=telegram.ReplyKeyboardRemove())
        db.close()
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Somehow I could not update your last contact date for this contact.",
                                 reply_markup=telegram.ReplyKeyboardRemove())


# function to be called after a user has replied that no contact was contacted today by typing
# "Nope, that's it for today" via custom keyboard or in any other way
def no_contacts_today(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Fair enough. Tomorrow you still have time to get in touch with your friends "
                                  "and relatives. See you!",
                             reply_markup=telegram.ReplyKeyboardRemove())


# function to directly remind user of due contacts
def remindme(update, context):
    # simply makes use of existing reminder function which is called as a job. So make use of
    # the feature that the jobqueue is available in the context and add a single job to be
    # executed directly
    context.job_queue.run_once(reminder, when=datetime.timedelta(seconds=1),
                               context=update.effective_chat.id)


# edit_contact conversation to edit
def edit_contact_start(update, context) -> int:
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Let's edit the information of one of your contacts. "
                                  "What is his or her name? Please tell me the first and last "
                                  "name as to separate words.",
                             reply_markup=telegram.ReplyKeyboardRemove())
    # point to edit_contact_name
    return 0


def edit_contact_name(update, context) -> int:
    # get first and last name from message
    [first, last] = update.message.text.split()
    # check if a database record exists
    try:
        global DB_PATH
        db = connect_database(DB_PATH)
        cur = db.cursor()
        # determine user_id from user table
        sql = '''SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You do not seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            user_id = result[0]
        # check if the entered contact exists in the contact database for the user with user_id
        sql = '''SELECT contact_id, interval, last_contact FROM contacts WHERE 
        user_id = ? AND first_name = ? and last_name = ?'''
        cur.execute(sql, (user_id, first, last))
        # user_id, first_name and last_name are UNIQUE in contacts table so we can be sure
        # that we will only fetch one entry in case it exists in the first place
        result = cur.fetchone()
        db.close()
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Something went wrong when querying your contact. Please try again.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
    if result is None:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="I am sorry. There is no contact with name {} {} registered "
                                      "for you. Are you sure that you spelled everything right? You can "
                                      "use the /printcontacts command to get a list of all contacts "
                                      "which you have registered.".format(first, last),
                                 reply_markup=telegram.ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        [contact_id, interval, last_contact] = result
    # if the code makes it till here, then the user and contact exists so continue the conversation
    # asking for the new interval
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Gotcha. Let's edit {} {}. How often per year do you want to "
                                  "contact him or her? Please enter an integer number.".format(first, last),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # save first and last name in the sql_dict so that we can user it later on in the conversation
    sql_dict["first_name"] = first
    sql_dict["last_name"] = last
    sql_dict["interval"] = interval
    sql_dict["last_contact"] = last_contact
    # point to edit_contact_interval
    return 1


def edit_contact_interval(update, context) -> int:
    global sql_dict, DB_PATH
    try:
        interval = int(365 / int(update.message.text))
    except Exception as ex:
        print(ex)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="You entered {}. But I asked you how often per year you want to get in "
                                      "touch with your contact. You have to enter a number. Let's try "
                                      "it again. How often per year do you want to get in touch with "
                                      "him or her.".format(update.effective_chat.id),
                                 reply_markup=telegram.ReplyKeyboardRemove())
        # point to edit_contact_interval
        return 1
    sql_dict["interval"] = interval
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Got it. So you want to get in touch with {0} {1} roughly every {2} days.\n"
                                  "If you remember the date when you had contact with {0} {1} for the last "
                                  "time, please write it back in the format YYYY-MM-DD. If you respond anything "
                                  "else, I will simply assume that you want to keep the old date"
                             .format(sql_dict["first_name"], sql_dict["last_name"], sql_dict["interval"]),
                             reply_markup=telegram.ReplyKeyboardRemove())
    # point to edit_contact_last_contact
    return 2


def edit_contact_last_contact(update, context) -> int:
    global sql_dict
    # try converting user input to datetime object and if successful update sql_dict
    try:
        last_contact_datetime = datetime.datetime.strptime(update.message.text, "%Y-%m-%d")
        sql_dict["last_contact"] = last_contact_datetime.strftime("%Y_%m_%d")
    # if this not successfull we won't touch sql_dict
    except ValueError as e:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Ok. We will simply keep your last contact date.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
    # then update the database
    try:
        db = connect_database(DB_PATH)
        cur = db.cursor()
        sql = ''' SELECT user_id FROM users WHERE chat_id = ?'''
        cur.execute(sql, (update.effective_chat.id,))
        result = cur.fetchone()
        if result is None:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You don't seem to be a registered user. Please register "
                                          "first using the /register command.",
                                     reply_markup=telegram.ReplyKeyboardRemove())
            return
        else:
            sql_dict["user_id"] = result[0]
        sql = '''UPDATE contacts
        SET interval = ?, last_contact = ?
        WHERE user_id = ? AND first_name = ? and last_name = ?'''
        cur.execute(sql, (sql_dict["interval"], sql_dict["last_contact"],
                          sql_dict["user_id"], sql_dict["first_name"], sql_dict["last_name"]))
        db.commit()
        db.close()

        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Done. {} {} has been updated"
                                 .format(sql_dict["first_name"], sql_dict["last_name"]),
                                 reply_markup=telegram.ReplyKeyboardRemove())
    except sqlite3.Error as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oops. Something went wrong. I could not update your contact. "
                                      "Please try again.",
                                 reply_markup=telegram.ReplyKeyboardRemove())
    return ConversationHandler.END


# main function
def main():

    # INITIALIZE TELEGRAM BOT
    # instantiate update and dispatcher and job queue
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    jobqueue = updater.job_queue

    # INITIALIZE DATABASE
    db = connect_database(DB_PATH)
    # create the tables if they don't exist already
    create_tables(db)
    db.close()

    # define all the handlers except conversation handlers
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help)
    activate_handler = CommandHandler('activate', activate)
    deactivate_handler = CommandHandler('deactivate', deactivate)
    print_contacts_handler = CommandHandler('printcontacts', print_contacts)
    last_contact_update_handler = MessageHandler(Filters.regex('I contacted \w+ \w+ today!'), last_contact_update)
    no_contacts_today_handler = MessageHandler(Filters.regex("Nope, that's it for today"), no_contacts_today)
    remindme_handler = CommandHandler('remindme', remindme)

    # define the conversation handlers
    register_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register),
                      MessageHandler(Filters.regex(r'Please register me!'), register)],
        states={
            REMINDER_TIME: [MessageHandler(Filters.text, reminder_time)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    edit_time_handler = ConversationHandler(
        entry_points=[CommandHandler('time', edit_reminder_time_start)],
        states={
            0: [MessageHandler(Filters.text, edit_reminder_time_end)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    new_contact_handler = ConversationHandler(
        entry_points=[CommandHandler('newcontact', new_contact)],
        states={
            FIRST_NAME: [MessageHandler(Filters.text, first_name)],
            LAST_NAME: [MessageHandler(Filters.text, last_name),
                        CommandHandler('skip', skip_last_name)],
            INTERVAL: [MessageHandler(Filters.text, interval)],
            LAST_CONTACT: [MessageHandler(Filters.text, last_contact)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    edit_contact_handler = ConversationHandler(
        entry_points=[CommandHandler('editcontact', edit_contact_start)],
        states={
            0: [MessageHandler(Filters.text, edit_contact_name)],
            1: [MessageHandler(Filters.text, edit_contact_interval)],
            2: [MessageHandler(Filters.text, edit_contact_last_contact)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    # add all handlers to the dispatcher
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(activate_handler)
    dispatcher.add_handler(deactivate_handler)
    dispatcher.add_handler(register_handler)
    dispatcher.add_handler(edit_time_handler)
    dispatcher.add_handler(new_contact_handler)
    dispatcher.add_handler(print_contacts_handler)
    dispatcher.add_handler(last_contact_update_handler)
    dispatcher.add_handler(no_contacts_today_handler)
    dispatcher.add_handler(remindme_handler)
    dispatcher.add_handler(edit_contact_handler)

    # add a jobs to the job queue for each registered user
    try:
        db = connect_database(DB_PATH)
        cur = db.cursor()
        sql = ''' SELECT chat_id, is_active, reminder_time FROM users'''
        cur.execute(sql)
        for ii, row in enumerate(cur.fetchall()):
            reminder_datetime = datetime.datetime.strptime(row[2], '%H:%M:%S').time()
            localtz = pytz.timezone(TIMEZONE)
            # replace timezone as PTB needs timezone-aware objects
            reminder_datetime_tz = reminder_datetime.replace(tzinfo=localtz)
            jobs[row[0]] = jobqueue.run_daily(reminder, time=reminder_datetime_tz, context=row[0], name=str(row[0]))
            #jobs.append(jobqueue.run_repeating(reminder, interval=5, first=2, context=row[0], name=str(row[0])))
            # disable job right away if is_active is False (i.e. == 0)
            if row[1] == 0:
                jobs[row[0]].enabled = False
    except sqlite3.Error as e:
        print(e)


    # START BOT
    print("[INFO] Starting Bot")
    updater.start_polling()
    print("[INFO] Bot is now listening")
    updater.idle()


main()
