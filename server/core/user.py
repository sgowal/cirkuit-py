import random
import string
import time

# Provides 8^(26*2) possible ids.
_ID_LENGTH = 8

_COMPUTER_USERNAME = [
    'Lewis', 'Sophie', 'Jack', 'Emma', 'Ryan', 'Lucy', 'James', 'Katie', 'Callum', 'Erin',
    'Cameron', 'Ellie', 'Daniel', 'Amy', 'Liam', 'Emily', 'Jamie', 'Chloe', 'Kyle', 'Olivia',
    'Matthew', 'Hannah', 'Logan', 'Jessica', 'Finlay', 'Grace', 'Adam', 'Ava', 'Alexander',
    'Rebecca', 'Dylan', 'Isla', 'Aiden', 'Brooke', 'Andrew', 'Megan', 'Ben', 'Niamh', 'Aaron',
    'Eilidh', 'Connor', 'Eva', 'Thomas', 'Abbie', 'Joshua', 'Skye', 'David', 'Aimee', 'Ross', 'Mia',
    'Luke', 'Ruby', 'Nathan', 'Anna', 'Charlie', 'Sarah', 'Ethan', 'Rachel', 'Aidan', 'Caitlin', 'Michael',
    'Lauren', 'John', 'Freya', 'Calum', 'Keira', 'Scott', 'Lily', 'Josh', 'Leah', 'Samuel', 'Holly',
    'Kieran', 'Millie', 'Fraser', 'Charlotte', 'William', 'Abigail', 'Oliver', 'Molly', 'Rhys', 'Kayla',
    'Sean', 'Zoe', 'Harry', 'Eve', 'Owen', 'Iona', 'Sam', 'Cara', 'Christopher', 'Ella', 'Euan', 'Evie',
    'Robert', 'Nicole', 'Kai', 'Morgan', 'Jay', 'Jenna', 'Jake', 'Madison', 'Lucas', 'Kayleigh', 'Jayden',
    'Summer', 'Tyler', 'Paige', 'Rory', 'Daisy', 'Reece', 'Taylor', 'Robbie', 'Amelia', 'Joseph', 'Zara',
    'Max', 'Beth', 'Benjamin', 'Amber', 'Ewan', 'Robyn', 'Archie', 'Georgia', 'Evan', 'Shannon', 'Leo',
    'Sophia', 'Taylor', 'Courtney', 'Alfie', 'Jennifer', 'Blair', 'Abby', 'Arran', 'Neve', 'Leon', 'Carly',
    'Angus', 'Casey', 'Craig', 'Elizabeth', 'Murray', 'Kaitlyn', 'Declan', 'Poppy', 'Zak', 'Melissa',
    'Brandon', 'Jasmine', 'Harris', 'Bethany', 'Finn', 'Abi', 'Lee', 'Gemma', 'Lennon', 'Laura', 'Cole',
    'Mya', 'George', 'Kara', 'Jacob', 'Orla', 'Mark', 'Elise', 'Hayden', 'Hayley', 'Kenzie', 'Kelsey',
    'Alex', 'Charley', 'Shaun', 'Imogen', 'Louis', 'Kirsty', 'Caleb', 'Rachael', 'Mason', 'Heather',
    'Gregor', 'Chelsea', 'Mohammed', 'Layla', 'Luca', 'Samantha', 'Harrison', 'Julia', 'Kian', 'Maya',
    'Noah', 'Natalie', 'Paul', 'Alice', 'Riley', 'Libby', 'Stuart', 'Rhianna', 'Joe', 'Rosie', 'Jonathan',
    'Stephen',
]


class User(object):

  def __init__(self, username=None):
    self.id = None if not username else ''.join(random.choice(string.ascii_letters) for _ in xrange(_ID_LENGTH))
    self.creation_date = int(time.time())
    self.refresh_date = int(time.time())
    self.username = username if username else (random.choice(_COMPUTER_USERNAME) + ' (cpu)')
    self.is_computer = username is None

  def __eq__(self, other):
    if self.id or other.id:
        return self.id == other.id
    return False

  def Refresh(self):
    self.refresh_date = int(time.time())
