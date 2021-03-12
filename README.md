# contact_reminder
a telegram bot that reminds you of people whom you want to stay in touch with

Tired of always forgetting to stay in touch with all the people you know. Here comes the solution!

This telegram bot allows you to:
- Define a list of people you would like to stay in touch with
- Set a contact interval
- Register your telegram account with the bot
- Set a time of the day when you want to be reminded

The bot will automatically send you a message every day with all the people you need to contact
according to your list. You can reply those people whom you contacted via an intuitive keyboard

How to use:
- Get a telegram bot from the BotFather and save its token
- Open the example configuration "example_config.conf", rename it and
  - Add your bot token
  - Set your name of choice for the database
  - Set the timezone in pytz format where the bot shall work in, e.g "Europe/Berlin"- 
- In contact_reminder.py set CONF_NAME to the name of your configuration file

Run the bot and contact him via telegram
