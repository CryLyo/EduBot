import discord
from discord.ext import commands
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import json
import io, os, sys, time
from enum import Enum
import emoji
import re

# Filepath data:
text_dir = "./text_files/"
assets_dir = "./assets/"

# Global functions and variables

get_emoji = lambda em: emoji.emojize(em, use_aliases=True)
lrev = lambda x: list(reversed(x))
emoji_options = [get_emoji(em) for em in
                              (":one:",":two:",":three:",":four:",":five:",":six:",":seven:",":eight:",":nine:",
                               "🔟", "\N{REGIONAL INDICATOR SYMBOL LETTER A}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER B}", "\N{REGIONAL INDICATOR SYMBOL LETTER C}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER D}", "\N{REGIONAL INDICATOR SYMBOL LETTER E}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER F}", "\N{REGIONAL INDICATOR SYMBOL LETTER G}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER H}", "\N{REGIONAL INDICATOR SYMBOL LETTER I}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER J}", "\N{REGIONAL INDICATOR SYMBOL LETTER K}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER L}", "\N{REGIONAL INDICATOR SYMBOL LETTER M}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER N}", "\N{REGIONAL INDICATOR SYMBOL LETTER O}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER P}", "\N{REGIONAL INDICATOR SYMBOL LETTER Q}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER R}", "\N{REGIONAL INDICATOR SYMBOL LETTER S}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER T}", "\N{REGIONAL INDICATOR SYMBOL LETTER U}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER V}", "\N{REGIONAL INDICATOR SYMBOL LETTER W}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER X}", "\N{REGIONAL INDICATOR SYMBOL LETTER Y}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER Z}")]
control_emojis = {"next": ":arrow_forward:",
                  "previous": ":arrow_backward:",
                  "multiple": ":1234:",
                  "dynamic": ":video_game:",
                  "finish": ":checkered_flag:",
                  "results": ":chart_with_upwards_trend:",
                  "refresh": ":arrows_counterclockwise:",
                  "cross": ":x:"
                  }
control_emojis = {key:get_emoji(val) for key, val in control_emojis.items()}

emoji_index = lambda em: emoji_options.index(str(em)) if str(em) in emoji_options else None


# Identifier to clarify code
class identifier(Enum):
    ID = 1
    Message_ID = 2
    Channel_ID = 3
    Guild_ID = 4
    Name = 5
    Title = 6
    Owner = 7

class colors(Enum):
    Blue = 0x0015FF
    Green = 0x00FF21
    Red = 0xFF0010
    Orange = 0xEA6500
    Yellow = 0xE0BB00
    Magenta = 0xCC0099
    Cyan = 0x00CBFF

class action(Enum):
    Close = 1
    Finish = 2
    Results = 3


class Quiz:
    instances = []

    # Framework functions
    def __init__(self):

        self.ID = 0

        # Add self to the instances dict following largest ID:
        if len(Quiz.instances) == 0:
            Quiz.instances.append(self)
        else:
            largest_ID = max([q.ID for q in Quiz.instances])
            self.ID = largest_ID + 1
            Quiz.instances.append(self)

        # Bookkeeping data
        self.quiz_title = "UNSPECIFIED QUIZ"
        self.message_ids = []
        self.channel_id = -1
        self.guild_id = -1

        # Quiz data
        self.single_vote = True
        self.dynamic = False
        self.question = ""
        self.options = []
        self.correct = -1
        self.alternative_thumbnail = ""

        # Answer data
        self.results = dict()

    def __repr__(self):
        return re.sub(r'\W+', '', f"Quiz_{self.ID}_{self.quiz_title}")

    @property
    def save_name(self):
        return re.sub(r'\W+', '', f"ID{self.ID}_{self.quiz_title.replace(' ', '_')}")

    def destroy(self):
        Quiz.instances.remove(self)
        del self

    def set_values(self, **kwargs):
        for key, val in kwargs.items():
            if key in self.__dict__:
                self.__dict__[key] = val
        self.validate_results_property()

    @classmethod
    def get_quizzes(cls, key, type=identifier.ID):
        inst_values = cls.instances
        switch = {
            identifier.ID : lambda val: [inst for inst in inst_values if inst.ID == val],
            identifier.Message_ID : lambda val: ([inst for inst in inst_values if val in inst.message_ids]),
            identifier.Channel_ID : lambda val: lrev([inst for inst in inst_values if inst.channel_id == val]),
            identifier.Guild_ID : lambda val: lrev([inst for inst in inst_values if inst.guild_id == val]),
            identifier.Title : lambda val: lrev([inst for inst in inst_values if inst.quiz_title == val])
        }
        return switch[type](key)

    @classmethod
    def get_quiz(cls, key, type=identifier.ID):
        return (cls.get_quizzes(key, type=type)+[None])[0]

    def validate_results_property(self):
        for i in range(len(self.options)):
            if not i in self.results:
                self.results[i] = set()

    def build_options_fields(self):
        field_titles = ["__Options__"]
        resulting_fields = ["\u200b"]

        to_build = []
        for i, option in enumerate(self.options):
            to_build.extend(f"{emoji_options[i]}**)** {self.options[i]}\n".split(" "))

        for sequence in to_build:
            to_check = sequence + " "
            if len(resulting_fields[-1]+to_check) > 1024:
                resulting_fields.append(to_check)
                field_titles.append("\u200b")
            else:
                resulting_fields[-1] += to_check
        return zip(field_titles, resulting_fields)

    def transform_to_dict(self):
        # Get all class variables as a dict
        dict_repr = {k:v for k, v in self.__dict__.items() if not (k.startswith('__') and k.endswith('__'))}
        # Transform the options variable to a list for proper json saving
        dict_repr["results"] = {key:list(val) for key,val in dict_repr["results"].items()}
        return dict_repr

    def construct_from_dict(self, dict_obj: dict):
        dict_copy = dict_obj.copy()
        if "results" in dict_copy:
            dict_copy["results"] = {int(key):set(val) for key,val in dict_obj["results"].items()}
        self.set_values(**dict_copy)

    # Actual quiz-related functions
    def vote(self, user, emoji):
        em_index = emoji_index(emoji)
        valid_vote = em_index < len(self.options) if (em_index is not None) else False

        if valid_vote:
            if self.single_vote:
                for result in self.results.values():
                    if user in result:
                        result.remove(user)
            self.results[em_index].add(user)
        return valid_vote

    def unvote(self, user, emoji):
        em_index = emoji_index(emoji)
        valid_vote = em_index < len(self.options) if em_index else False

        if valid_vote:
            if user in self.results[em_index]:
                self.results[em_index].remove(user)

        return valid_vote

    def add_option(self, user, option):
        self.options.append(option)
        self.validate_results_property()
        self.vote(user, emoji_options[len(self.options) - 1])

    def render_graph(self):
        image_buffer = io.BytesIO()
        image_buffer.name = re.sub(r'\W+', '', f"feedback_QUIZ{self.ID}_{self.quiz_title.replace(' ','_')}")+".png"

        # Easier on the eyes
        plt.style.use('dark_background')

        width = 0.25

        summed_results = [len(res) for res in self.results.values()]
        explode_values = [0.3 if i==self.correct else 0 for i in range(len(self.options))] \
            if self.correct >= 0 \
            else None
        pie, labtext = plt.pie(summed_results, explode=explode_values, shadow=True)
        plt.setp(pie, width=width)
        plt.legend(labels=self.options)

        # Save to buffer
        plt.savefig(image_buffer, format="png", bbox_inches="tight", transparent=True)
        plt.close()

        image_buffer.seek(0)
        return image_buffer

    def generate_quiz_embed(self):
        embed = discord.Embed(
            title=f"Quiz {self.ID+1}: {self.quiz_title}",
            color=colors.Blue.value,
            description="Quiz time! Take a look at the question below."
        )
        embed.set_author(name="EduBot Quiz System",
                         icon_url="attachment://quiz_icon.png",
                         url="https://www.python.org/")

        thumbnail_url = self.alternative_thumbnail if len(self.alternative_thumbnail) > 0 else "quiz_thumbnail.png"
        embed.set_thumbnail(url=f"attachment://{thumbnail_url}")

        thumbnail_url = assets_dir+"quiz_thumbnail.png" if \
            len(self.alternative_thumbnail)==0 else \
            QuizViewer.filepath.joinpath(self.alternative_thumbnail)

        # Add field for question
        embed.add_field(name="__Question__", value=f"**{self.question}**")

        # Add answer options
        option_data = self.build_options_fields()
        for title, field in option_data:
            embed.add_field(name=title, value=field, inline=False)

        if self.dynamic:
            embed.add_field(name="__Dynamic__", value="This quiz is **dynamic**! Add your own option via "
                                                      "**!add** *<option>*.", inline=False)

        embed.set_footer(
            text=f"Respond with the emoji's below! "
                 f"{'Only your final vote counts.' if self.single_vote else 'Multiple votes are allowed.'}"
        )

        # Load required files
        attachments = []
        for file in (assets_dir+"quiz_icon.png", thumbnail_url):
            try:
                attachments.append(discord.File(file))
            except:
                continue

        return embed, attachments

    def generate_feedback_embed(self):
        embed, attachments = self.generate_quiz_embed()
        feedback_graph = self.render_graph()

        embed_dict = embed.to_dict()
        embed_dict["color"] = colors.Green.value
        embed = discord.Embed().from_dict(embed_dict)

        embed.set_footer()
        embed.add_field(name="__Feedback__", value="\u200b")
        embed.set_image(url=f"attachment://{feedback_graph.name}")

        attachments.append(discord.File(feedback_graph))

        return embed, attachments

class QuizCreator:
    instances = {}
    def __init__(self):
        self.owner = -1
        self.message_id = -1

        # Widget data
        self.page_nr = 0

        # Hard-coded standard pages as opposed to loaded in from text file
        self.standard_pages = [('__Overview__',
                                'The quiz system provides an interactive quiz/polling environment right here in '
                                'Discord!\n\nQuizzes are defined  beforehand using the quiz creation wizard and are '
                                'stored in the bot for future use. When a quiz is started, the quiz system will create '
                                'and manage an auto-generated quiz message in the specified channel and set up voting '
                                'immediately. \nQuiz parameters that can be defined are the quiz title, answer options,'
                                ' correct answer, voting style and dynamic mode *(allowing users to add their own '
                                'answers to the options list, off by default)*\n\n'),
                               ('__Voting__',
                                "Users are able to vote by clicking the emoji's provided at the bottom of the quiz "
                                "message. There are two voting styles: \n- **Single-vote** *(default)* : only the final"
                                " vote counts, vote changes are handled automatically.\n- **Multi-vote** : users can "
                                "vote on multiple options and have to de-select their votes manually if their opinion"
                                " changes. \n\n"),
                               ('__Control Widget__',
                                'Once the quiz is started, the organizer of the quiz will receive a control widget '
                                'via a private message. This widget provides limited control over the quiz while it '
                                'is running as some parameters such as the title and answer options are locked at this '
                                'time. The following parameters and behaviour can be controlled:\n- **Voting style** : '
                                'change between single-vote and multi-vote.\n- **Marking correct answer** : if a new '
                                'correct answer is marked, it overwrites the one specified during quiz creation *(if '
                                'applicable)*.\n- **Toggle Dynamic mode** : toggle the user ability to add new answer '
                                'options using the **!add** *<option>* command.\n- **Intermediate Feedback** : generate'
                                ' an intermediate feedback graph and send via private message.\n- **Finish quiz** : '
                                'generate the feedback graph and finish the quiz, this is irreversible.\nMore '
                                'information on how to change the parameters is given in the control widget.\nThe '
                                'control widget will be deleted once the quiz is finished.\n\n'),
                               ('__Commands__',
                                "Configure your quiz using the following commands:\n-**!load** *<quiz id>* : load a "
                                "previously created quiz for editing. Quiz ID's can be found using the "
                                "**!view_quizzes** command.\n-**!set_title** *<title>* : this title will be "
                                "displayed at the top of your quiz.\n-**!set_question** *<question>* : set the "
                                "question that you want to ask in your quiz. \n-**!add_option** *<option>* : add an"
                                " option to your answer options.\n-**!remove_option** *<option number>* : remove an"
                                " option from your answer options.\n-**!edit_option** *<option number>* *<new value>*"
                                " : change an answer option.\n-**!mark_correct** *<option number>* : mark the given"
                                " option number as the correct answer.\n-**!set_image** *<attach file to message>* :"
                                " only one image can be set per quiz. If none is provided, the standard image is used"
                                " instead.\n-**!finish** : finish the creation of the quiz and save it on the bot for"
                                " future use.\n\nIn addition, the emoji's below can be clicked to toggle voting"
                                " style (1234) and dynamic mode (game controller).")]


        self.control_emojis = {
            control_emojis["previous"]: self.previous_page,
            control_emojis["next"]: self.next_page,
            control_emojis["multiple"]: self.toggle_single,
            control_emojis["dynamic"]: self.toggle_dynamic,
            control_emojis["cross"]: (lambda: action.Close)
        }

        # Data for the quiz that is being created
        self.quiz_title = "[Specify Title]"
        self.question = "[Specify Question]"
        self.options = []
        self.correct = -1
        self.single_vote = True
        self.dynamic = False
        self.alternative_thumbnail = ""

        self.unique_identifier = time.strftime("%y%m%d%H%M%S")+str(self.owner)

    def register(self, id):
        QuizCreator.instances[id] = self
        self.message_id = id
        return self

    @property
    def save_name(self):
        return self.unique_identifier

    def construct_from_dict(self, dict_obj: dict):
        self.set_values(**dict_obj)
        self.register(dict_obj["message_id"])

    def toggle_single(self):
        self.single_vote = not self.single_vote
    def toggle_dynamic(self):
        self.dynamic = not self.dynamic

    @classmethod
    def get_creators(cls, key, type=identifier.Owner):
        inst_values = cls.instances.values()
        switch = {
            identifier.Message_ID: lambda val: [cls.instances[val] if val in cls.instances else None],
            identifier.Owner: lambda val: lrev([inst for inst in inst_values if inst.owner == val])
        }
        return switch[type](key)

    @classmethod
    def get_creator(cls, key, type=identifier.Owner):
        return (cls.get_creators(key, type=type) + [None])[0]


    def destroy(self):
        QuizCreator.instances.pop(self.message_id)
        del self

    # Verify that a message id belongs to a QuizCreator object belonging to a given owner
    def verify(self, message_id):
        return message_id == self.message_id

    def set_values(self, **kwargs):
        for key, val in kwargs.items():
            if key in self.__dict__:
                self.__dict__[key] = val

    def transform_to_dict(self):
        filename, savedict = self.finalize_quiz()
        savedict["owner"] = self.owner
        savedict["message_id"] = self.message_id
        savedict["page_nr"] = self.page_nr
        return savedict

    def next_page(self):
        self.page_nr = (self.page_nr+1)%(len(self.standard_pages)+1)
    def previous_page(self):
        self.page_nr = (self.page_nr-1)%(len(self.standard_pages)+1)

    def handle_input(self, emoji):
        function_output = None
        if str(emoji) in self.control_emojis:
            function_output = self.control_emojis[str(emoji)]()

        return (*self.generate_creation_embed(), function_output)

    def finalize_quiz(self):
        file_name = self.unique_identifier+".json"
        to_save = dict(
            quiz_title=self.quiz_title,
            question=self.question,
            options=self.options,
            correct=self.correct,
            alternative_thumbnail=self.alternative_thumbnail,
            single_vote=self.single_vote,
            dynamic=self.dynamic,
            unique_identifier=self.unique_identifier
        )
        return file_name, to_save

    def build_options_fields(self):
        field_titles = ["**Answer Options:**"]
        resulting_fields = [""]

        if len(self.options) == 0:
            return [("**Answer Options:**","*1) [Begin adding options using **!add_option**]*")]

        to_build = []
        for i, option in enumerate(self.options):
            to_build.extend(f'*{i + 1}) {option}*\n'.split(" "))

        for sequence in to_build:
            to_check = sequence + " "
            if len(resulting_fields[-1] + to_check) > 1024:
                resulting_fields.append(to_check)
                field_titles.append("\u200b")
            else:
                resulting_fields[-1] += to_check

        return zip(field_titles, resulting_fields)

    def generate_creation_embed(self):
        embed = discord.Embed(title="Quiz Creation Wizard",
                              description="**This wizard will assist you in your quiz creation effort! "
                                          "Look at the sections below for information on how to proceed**",
                              color=colors.Orange.value)
        embed.set_author(name="EduBot Quiz System",
                         icon_url="attachment://quiz_icon.png",
                         url="https://www.python.org/")
        embed.set_footer(text=f"Click the arrow emoji's below to navigate the different pages."
                              f"\t({self.page_nr+1}/{len(self.standard_pages)+1})")
        embed.set_thumbnail(url="attachment://quiz_creation_thumbnail.png")

        if self.page_nr < len(self.standard_pages):
            page_title, page_content = self.standard_pages[self.page_nr]
            embed.add_field(name=page_title, value=page_content, inline=False)
        else:
            page_title = "__Quiz Data__"
            top_half = f"""
                    **Quiz Title:** {self.quiz_title}
                    **Question:** {self.question}
                    """
            bottom_half = f"""
                    **Correct answer:** {'Not set' if self.correct < 0 else self.correct + 1}
                    **Voting style:** {'Single-vote' if self.single_vote else 'Multi-vote'}
                    **Dynamic mode:** {'Enabled' if self.dynamic else 'Disabled'}
                    **Custom image:** {'Set' if len(self.alternative_thumbnail) > 0 else 'Not set'}
                    """
            embed.add_field(name=page_title, value=top_half, inline=False)

            answer_data = self.build_options_fields()
            for title, option in answer_data:
                embed.add_field(name=title, value=option, inline=False)

            embed.add_field(name="\u200b", value=bottom_half, inline=False)



        # Load required files
        attachments = []
        for file in ("quiz_icon.png", "quiz_creation_thumbnail.png"):
            try:
                attachments.append(discord.File(assets_dir + file))
            except:
                continue

        return embed, attachments

class QuizViewer:
    instances = {}
    filepath = None
    def __init__(self):
        self.owner = -1
        self.message_id = -1
        self.page_nr = 0
        self.pages = []
        self.last_refresh = "Never"

        self.control_emojis = {
            control_emojis["previous"]: self.previous_page,
            control_emojis["next"]: self.next_page,
            control_emojis["refresh"]: self.refresh,
            control_emojis["cross"]: (lambda: action.Close)
        }

        # Build up the initial database
        self.refresh()

    def register(self, id):
        QuizViewer.instances[id] = self
        self.message_id = id
        return self

    @property
    def save_name(self):
        return str(self.message_id)

    def construct_from_dict(self, dict_obj: dict):
        self.set_values(**dict_obj)
        self.register(dict_obj["message_id"])

    @classmethod
    def get_viewers(cls, key, type=identifier.Owner):
        inst_values = cls.instances.values()
        switch = {
            identifier.Message_ID: lambda val: [cls.instances[val] if val in cls.instances else None],
            identifier.Owner: lambda val: lrev(([inst for inst in inst_values if inst.owner == val]))
        }
        return switch[type](key)

    @classmethod
    def get_viewer(cls, key, type=identifier.Owner):
        return (cls.get_viewers(key, type=type) + [None])[0]

    @classmethod
    def load_quiz_file(cls, id):
        # This function assumes that the given id exists
        file = sorted([file for file in os.listdir(cls.filepath) if not file.endswith(".png")])[id]
        to_return = None
        with open(QuizViewer.filepath.joinpath(file), "r") as json_file:
            to_return = json.load(json_file)
        return to_return

    def destroy(self):
        QuizViewer.instances.pop(self.message_id)
        del self

    # Verify that a message id belongs to a QuizViewer object belonging to a given owner
    def verify(self, message_id):
        return message_id == self.message_id

    def set_values(self, **kwargs):
        for key, val in kwargs.items():
            if key in self.__dict__:
                self.__dict__[key] = val

    def transform_to_dict(self):
        to_return = dict(
            owner=self.owner,
            message_id=self.message_id,
            page_nr=self.page_nr
        )
        return to_return

    def next_page(self):
        self.page_nr = (self.page_nr+1)%(len(self.pages))
    def previous_page(self):
        self.page_nr = (self.page_nr-1)%(len(self.pages))

    def handle_input(self, emoji):
        function_output = None
        if str(emoji) in self.control_emojis:
            function_output = self.control_emojis[str(emoji)]()

        return (*self.generate_viewer_embed(), function_output)

    def refresh(self):
        self.page_nr = 0
        files = sorted([file for file in os.listdir(QuizViewer.filepath) if not file.endswith(".png")])

        template = "{:<10} {:<20} {:<15}\n"
        starter_string = template.format("*ID*", "*Quiz Title*", "*Quiz Question*")
        records = [starter_string]
        for i, file in enumerate(files):
            with open(QuizViewer.filepath.joinpath(file), "r") as jsonfile:
                json_data = json.load(jsonfile)
            cut_title = json_data["quiz_title"]
            cut_title = cut_title if len(cut_title) <= 20 else cut_title[:17].rstrip()+"..."
            cut_question = json_data["question"]
            cut_question = cut_question if len(cut_question) <= 15 else cut_question[:13].rstrip()+"...?"

            record_string = template.format(i, cut_title, cut_question)

            if len(record_string) + len(records[-1]) > 1024:
                records.append(starter_string + record_string)
            else:
                records[-1] += record_string

        self.pages = [("__Quizzes__", record) for record in records]
        self.last_refresh = time.strftime("%H:%M:%S - %d/%m/%Y")
        return len(files) - 1

    def remove_quiz(self, id):
        files = sorted([file for file in os.listdir(QuizViewer.filepath) if not file.endswith(".png")])
        if id >= len(files):
            return False
        else:
            file = files[id]
            os.remove(QuizViewer.filepath.joinpath(file))
            possible_png = QuizViewer.filepath.joinpath(file.rstrip(".json")+".png")
            if possible_png.exists():
                os.remove(possible_png)
            return True

    def generate_viewer_embed(self):
        embed = discord.Embed(title="Quiz Viewer",
                              description="With this widget you can view all quizzes currently stored into memory. "
                                          "The ID's used here can be used in the **!load** *id* and **!start_quiz** "
                                          "*id* commands! You can also use the ID in the **!remove_quiz** *id* command, "
                                          "but keep in mind this permanently removes the quiz from memory.",
                              color=colors.Magenta.value)
        embed.set_author(name="EduBot Quiz System",
                         icon_url="attachment://quiz_icon.png",
                         url="https://www.python.org/")

        embed.set_thumbnail(url="attachment://quiz_viewer_thumbnail.png")
        embed.set_footer(text=f"Click the arrow emoji's below to navigate the different pages."
                              f"\t({self.page_nr + 1}/{len(self.pages)}) \nLast update: {self.last_refresh}")

        page_title, page_content = self.pages[self.page_nr]
        embed.add_field(name=page_title, value="```"+page_content+"```")

        attachments = []
        for file in ("quiz_viewer_thumbnail.png", "quiz_icon.png"):
            attachments.append(discord.File(assets_dir + file))

        return embed, attachments

class ControlWidget:
    instances = {}
    quiz_channels=[]

    def __init__(self):
        self.owner = -1
        self.tracking_id = -1
        self.message_id = -1

        self.control_emojis = {
            control_emojis["multiple"]: self.toggle_votingstyle,
            control_emojis["dynamic"]: self.toggle_dynamic,
            control_emojis["results"]: (lambda: action.Results),
            control_emojis["finish"]: (lambda: action.Finish)
        }

        self.started = False

    def register(self, id):
        ControlWidget.instances[id] = self
        self.message_id = id
        return self

    @property
    def save_name(self):
        return str(self.message_id)

    def construct_from_dict(self, dict_obj: dict):
        self.set_values(**dict_obj)
        self.register(dict_obj["message_id"])

    def toggle_votingstyle(self):
        quiz = Quiz.get_quiz(self.tracking_id)
        quiz.single_vote = not quiz.single_vote

    def toggle_dynamic(self):
        quiz = Quiz.get_quiz(self.tracking_id)
        quiz.dynamic = not quiz.dynamic

    @classmethod
    def get_widgets(cls, key, type=identifier.Owner):
        inst_values = cls.instances.values()
        switch = {
            identifier.Message_ID: lambda val: [cls.instances[val] if val in cls.instances else None],
            identifier.Owner: lambda val: lrev([inst for inst in inst_values if inst.owner == val])
        }
        return switch[type](key)

    @classmethod
    def get_widget(cls, key, type=identifier.Owner):
        return (cls.get_widgets(key, type=type) + [None])[0]

    def destroy(self):
        ControlWidget.instances.pop(self.message_id)
        del self

    # Verify that a message id belongs to a ControlWidget object belonging to a given owner
    def verify(self, message_id):
        return message_id == self.message_id

    def set_values(self, **kwargs):
        for key, val in kwargs.items():
            if key in self.__dict__:
                self.__dict__[key] = val

    def transform_to_dict(self):
        to_return = dict(owner=self.owner,
                         tracking_id=self.tracking_id,
                         message_id=self.message_id,
                         started=self.started
                         )
        return to_return

    def handle_input(self, emoji):
        function_output = None
        if str(emoji) in self.control_emojis:
            function_output = self.control_emojis[str(emoji)]()

        return (*self.generate_widget_embed(), function_output)

    def generate_widget_embed(self):
        embed = discord.Embed(title="Quiz Control Widget",
                              description="With this widget you can control your current running quiz!",
                              color=colors.Blue.value)
        embed.set_author(name="EduBot Quiz System",
                         icon_url="attachment://quiz_icon.png",
                         url="https://www.python.org/")

        embed.set_thumbnail(url="attachment://quiz_thumbnail.png")

        if self.started:
            embed.set_footer(
                text=f"Click the emoji's below to toggle voting style and dynamic mode, generate intermediate "
                     f"feedback or to finish the quiz.")
            quiz = Quiz.get_quiz(self.tracking_id)
            quiz_data = f"""
            **Quiz display number:** {quiz.ID+1}
            **Quiz status:** active
            **Voting style:** {'Single-vote' if quiz.single_vote else 'Multi-vote'}
            **Dynamic mode:** {'Enabled' if quiz.dynamic else 'Disabled'}
            **Correct answer:** {'Not set' if quiz.correct < 0 else quiz.correct + 1}
            """
            embed.add_field(name="__Quiz Data__", value=quiz_data, inline=False)
            embed.add_field(name="__Control__", value="**!change_correct** *<option number>*: "
                                                        "change the correct answer.", inline=False)
        else:
            pre_text = "Choose a channel below to start the quiz via the **!select_channel** *<number>*.\n"
            channels = "\n".join([f"{i+1}) #{name}" for i, name in enumerate(ControlWidget.quiz_channels)])
            embed.add_field(name="__Instructions__",value=pre_text+channels, inline=False)

        attachments = []
        for file in ("quiz_thumbnail.png", "quiz_icon.png"):
            attachments.append(discord.File(assets_dir + file))

        return embed, attachments


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.datadir = bot.datadir.joinpath("quiz_data")
        if not self.datadir.exists():
            self.datadir.mkdir()

        self.bot_loaded = False
        # Extra path definitions
        self.quiz_save_dir = self.datadir.joinpath("saved_quizzes")
        self.creator_save_dir = self.datadir.joinpath("saved_creators")
        self.viewer_save_dir = self.datadir.joinpath("saved_viewers")
        self.widget_save_dir = self.datadir.joinpath("saved_control_widgets")
        self.config_file = self.datadir.joinpath("quiz_channels.txt")
        self.storagedir = self.datadir.joinpath("storage")

        if not self.storagedir.exists():
            self.storagedir.mkdir()
        if not self.quiz_save_dir.exists():
            self.quiz_save_dir.mkdir()
        if not self.creator_save_dir.exists():
            self.creator_save_dir.mkdir()
        if not self.viewer_save_dir.exists():
            self.viewer_save_dir.mkdir()
        if not self.widget_save_dir.exists():
            self.widget_save_dir.mkdir()

        QuizViewer.filepath = self.storagedir

        self.quiz_channels = []
        self.load_all()
        self.load_channellist()


    @commands.Cog.listener()
    async def on_ready(self):
        print("Quiz Cog loaded.")
        self.bot_loaded = True
        ControlWidget.quiz_channels = [self.bot.get_channel(chan).name for chan in self.quiz_channels]


    def cog_unload(self):
        Quiz.instances = []
        QuizCreator.instances = {}
        QuizViewer.instances = {}
        ControlWidget.instances = {}
        print("Unloading Quiz Cog.")
        return super().cog_unload()

    def admin_check(self, ctx):
        for guild in self.bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and member.guild_permissions.administrator:
                return True
        return False

    def save_object(self, to_save):
        save_locations = {
            Quiz: self.quiz_save_dir,
            QuizViewer: self.viewer_save_dir,
            QuizCreator: self.creator_save_dir,
            ControlWidget: self.widget_save_dir
        }

        file_path = save_locations[type(to_save)].joinpath(to_save.save_name + ".json")
        with open(file_path, "w") as file:
            json.dump(to_save.transform_to_dict(), file, indent=2)

    def remove_save_file(self, object_to_remove):
        save_locations = {
            Quiz: self.quiz_save_dir,
            QuizViewer: self.viewer_save_dir,
            QuizCreator: self.creator_save_dir,
            ControlWidget: self.widget_save_dir
        }
        file_path = save_locations[type(object_to_remove)].joinpath(object_to_remove.save_name + ".json")
        os.remove(file_path)

    def load_all(self):
        print("Loading saved quizzes and widgets.")

        objecttypes = (Quiz, QuizCreator, QuizViewer, ControlWidget)
        paths = (self.quiz_save_dir, self.creator_save_dir, self.viewer_save_dir, self.widget_save_dir)

        for i, path in enumerate(paths):
            files_found = [file for file in os.listdir(path) if file.endswith(".json")]
            for file in files_found:
                file_path = path.joinpath(file)
                with open(file_path, "r") as sfile:
                    recovered_dict = json.load(sfile)
                    new_obj = objecttypes[i]().construct_from_dict(recovered_dict)

    def save_channellist(self):
        print("Saving Quiz channel list.")
        with open(self.config_file, "w") as file:
            file.writelines([str(val)+"\n" for val in self.quiz_channels])

    def load_channellist(self):
        if not self.config_file.exists():
            return
        print("Loading Quiz channel list.")

        with open(self.config_file, "r") as file:
            loaded_data = [int(line) for line in file.readlines() if len(line) > 0]
        self.quiz_channels = loaded_data

        if self.bot_loaded:
            ControlWidget.quiz_channels = [self.bot.get_channel(chan).name for chan in self.quiz_channels]

    # Adding an option to a quiz
    @commands.guild_only()
    @commands.command("add")
    async def add_to_dynamic(self, ctx, *args):
        to_add = " ".join(args)
        quiz = Quiz.get_quiz(ctx.channel.id, type=identifier.Channel_ID)
        if quiz:
            if quiz.dynamic:
                quiz.add_option(ctx.author.id, to_add)
                channel = self.bot.get_channel(quiz.channel_id)

                message_id_to_fetch = max(0,(len(quiz.options)-1)//20)
                if message_id_to_fetch >= len(quiz.message_ids):
                    new_message = await channel.send("\u200b")
                    quiz.message_ids.append(new_message.id)

                message = await channel.fetch_message(quiz.message_ids[0])
                react_message = await channel.fetch_message(quiz.message_ids[-1])

                await react_message.add_reaction(emoji_options[len(quiz.options) - 1])
                embed, files = quiz.generate_quiz_embed()
                await message.edit(embed=embed)
                self.save_object(quiz)

    # Emoji handling
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reactionevent):
        if reactionevent.user_id == self.bot.user.id:
            return

        # Check if the reaction was on a quiz
        quiz = Quiz.get_quiz(reactionevent.message_id, type=identifier.Message_ID)
        if quiz:
            valid_emoji = quiz.vote(reactionevent.user_id, reactionevent.emoji)

            if not valid_emoji:
                reaction_channel = self.bot.get_channel(reactionevent.channel_id)
                reaction_message = await reaction_channel.fetch_message(reactionevent.message_id)
                reaction_member = reaction_channel.guild.get_member(reactionevent.user_id)
                await reaction_message.remove_reaction(reactionevent.emoji, reaction_member)
            return

        # If not, check if it is a creator widget
        creator = QuizCreator.get_creator(reactionevent.message_id, type=identifier.Message_ID)
        valid = creator.verify(reactionevent.message_id) if creator else False
        if valid:
            embed, files, f_out = creator.handle_input(reactionevent.emoji)
            channel = self.bot.get_user(reactionevent.user_id)
            message = await channel.fetch_message(reactionevent.message_id)
            if f_out == action.Close:
                await message.delete()
                self.remove_save_file(creator)
                creator.destroy()
            else:
                await message.edit(embed=embed)
            return

        # If not, check if it is a viewer widget
        viewer = QuizViewer.get_viewer(reactionevent.message_id, type=identifier.Message_ID)
        valid = viewer.verify(reactionevent.message_id) if viewer else False
        if valid:
            embed, files, f_out = viewer.handle_input(reactionevent.emoji)
            channel = self.bot.get_user(reactionevent.user_id)
            message = await channel.fetch_message(reactionevent.message_id)
            if f_out == action.Close:
                await message.delete()
                self.remove_save_file(viewer)
                viewer.destroy()
            else:
                await message.edit(embed=embed)
            return

        # If not, check if it is a control widget
        widget = ControlWidget.get_widget(reactionevent.message_id, type=identifier.Message_ID)
        valid = widget.verify(reactionevent.message_id) if widget else False
        if valid:
            embed, files, f_out = widget.handle_input(reactionevent.emoji)
            channel = self.bot.get_user(reactionevent.user_id)
            message = await channel.fetch_message(reactionevent.message_id)

            quiz = Quiz.get_quiz(widget.tracking_id)
            quiz_channel = self.bot.get_channel(quiz.channel_id)
            quiz_messages = [await quiz_channel.fetch_message(mid) for mid in quiz.message_ids]

            if f_out == action.Finish:
                await message.delete()
                quiz_embed, quiz_files = quiz.generate_feedback_embed()

                for quiz_message in quiz_messages:
                    await quiz_message.delete()

                await quiz_channel.send(embed=quiz_embed, files=quiz_files)

                self.remove_save_file(widget)
                self.remove_save_file(quiz)
                quiz.destroy()
                widget.destroy()
            elif f_out == action.Results:
                await channel.send(f"<@{reactionevent.user_id}> Here is the requested intermediate feedback!",
                                   file=discord.File(quiz.render_graph()),
                                   delete_after=30)
            else:
                await message.edit(embed=embed)
                quiz_embed, quiz_files = quiz.generate_quiz_embed()
                await quiz_messages[0].edit(embed=quiz_embed)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, reactionevent):
        if reactionevent.user_id == self.bot.user.id:
            return

        # Check if the reaction was on a quiz
        quiz = Quiz.get_quiz(reactionevent.message_id, type=identifier.Message_ID)
        if quiz:
            quiz.unvote(reactionevent.user_id, reactionevent.emoji)
            return

        await self.on_raw_reaction_add(reactionevent)

    # Quiz creation commands
    @commands.dm_only()
    @commands.command("create_quiz", aliases=("create-quiz","createquiz"))
    async def creation_create_quiz(self, ctx):
        if not self.admin_check(ctx):
            return

        new_creator = QuizCreator()
        embed, files = new_creator.generate_creation_embed()
        private_message = await self.bot.dm(ctx.author.id, "", embed=embed, files=files)
        new_creator.register(private_message.id)
        new_creator.set_values(owner=ctx.author.id)
        for em in new_creator.control_emojis.keys():
            await private_message.add_reaction(em)

        self.save_object(new_creator)


    @commands.dm_only()
    @commands.command("set_title", aliases=("set-title", "settitle"))
    async def creation_set_title(self, ctx, *args):
        if not self.admin_check(ctx):
            return
        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            new_title = " ".join(args)
            creator.quiz_title = new_title

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)

    @commands.dm_only()
    @commands.command("set_question", aliases=("set-question", "setquestion"))
    async def creation_set_question(self, ctx, *args):
        if not self.admin_check(ctx):
            return
        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            new_question = " ".join(args)
            creator.question = new_question

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    @commands.dm_only()
    @commands.command("add_option", aliases=("add-option", "addoption"))
    async def creation_add_option(self, ctx, *args):
        if not self.admin_check(ctx):
            return
        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            new_option = " ".join(args)
            creator.options.append(new_option)

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    @commands.dm_only()
    @commands.command("remove_option", aliases=("remove-option", "removeoption"))
    async def creation_remove_option(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            if len(creator.options) <= int(id) - 1:
                return
            creator.options.pop(int(id) - 1)

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    @commands.dm_only()
    @commands.command("edit_option", aliases=("edit-option", "editoption"))
    async def creation_edit_option(self, ctx, id, *args):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            if len(creator.options) <= (int(id) - 1):
                return
            edited_option = " ".join(args)
            creator.options[int(id) - 1] = edited_option

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    @commands.dm_only()
    @commands.command("mark_correct", aliases=("mark-correct", "markcorrect"))
    async def creation_mark_correct(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            if len(creator.options) < int(id):
                return
            creator.correct = int(id) - 1

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    @commands.dm_only()
    @commands.command("set_image", aliases=("set-image", "setimage"))
    async def creation_set_image(self, ctx):
        if not self.admin_check(ctx):
            return
        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            file_name = creator.unique_identifier + ".png"

            if len(ctx.message.attachments) > 0:
                # Modern systems are not at all bothered if a jpg is saved as png, so we don't check filetype
                await ctx.message.attachments[0].save(self.storagedir.joinpath(file_name), use_cached=False,
                                                      seek_begin=True)
                creator.set_values(alternative_thumbnail=file_name)
            else:
                creator.set_values(alternative_thumbnail="")
                if self.storagedir.joinpath(file_name).exists():
                    os.remove(self.storagedir.joinpath(file_name))

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)


    @commands.dm_only()
    @commands.command("finish")
    async def creation_done(self, ctx):
        if not self.admin_check(ctx):
            return
        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            file_name, final_dict = creator.finalize_quiz()
            with open(self.storagedir.joinpath(file_name), "w") as file:
                json.dump(final_dict, file, indent=2)

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            await message.channel.send(f"<@{ctx.author.id}> The quiz has been saved! To create a new quiz, use the "
                                       f"**!create_quiz** command again to generate another wizard. View all saved "
                                       f"quizzes using **!view_quizzes**.",
                                       delete_after=30)
            await message.delete()
            self.remove_save_file(creator)
            creator.destroy()

    @commands.dm_only()
    @commands.command("load")
    async def creation_load(self, ctx, id):
        if not id.isdigit():
            return

        if not self.admin_check(ctx):
            return

        creator = QuizCreator.get_creator(ctx.author.id)
        if creator:
            quiz_to_load = int(id)
            saved_quizzes = sorted([file for file in os.listdir(self.storagedir) if not file.endswith(".png")])
            if len(saved_quizzes) <= quiz_to_load:
                return
            with open(self.storagedir.joinpath(saved_quizzes[quiz_to_load]), "r") as file:
                loaded_dict = json.load(file)

            creator.set_values(**loaded_dict)

            message = await ctx.author.dm_channel.fetch_message(creator.message_id)
            embed, files = creator.generate_creation_embed()
            await message.edit(embed=embed)
            self.save_object(creator)

    # Quiz Viewing
    @commands.dm_only()
    @commands.command("view_quizzes", aliases=("view-quizzes", "viewquizzes"))
    async def view_quizzes(self, ctx):
        if not self.admin_check(ctx):
            return
        if len(os.listdir(self.storagedir)) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> There are no quizzes in memory!",
                             delete_after=30)
            return


        new_viewer = QuizViewer()
        embed, files = new_viewer.generate_viewer_embed()

        private_message = await self.bot.dm(ctx.author.id, "", embed=embed, files=files)
        new_viewer.register(private_message.id)
        new_viewer.set_values(owner=ctx.author.id)
        for em in new_viewer.control_emojis.keys():
            await private_message.add_reaction(em)

        self.save_object(new_viewer)



    @commands.dm_only()
    @commands.command("remove_quiz", aliases=("remove-quiz","removequiz"))
    async def remove_quiz(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        viewer = QuizViewer.get_viewer(ctx.author.id)
        if viewer:
            viewer.refresh()
            message = await ctx.author.dm_channel.fetch_message(viewer.message_id)
            embed, files = viewer.generate_viewer_embed()
            await message.edit(embed=embed)

            success = viewer.remove_quiz(int(id))
            if not success:
                await ctx.channel.send(f"<@{ctx.author.id}> There is no quiz with that ID!",
                                       delete_after=30)
            else:
                await ctx.channel.send(f"<@{ctx.author.id}> Quiz removed successfully!",
                                       delete_after=30)

        else:
            await ctx.channel.send(f"<@{ctx.author.id}> There is no viewer active! Please activate a quiz viewer using "
                                   f"**!view_quizzes** and try again. This is to avoid out-of-date quiz ID's.",
                                   delete_after=30)

    # # Starting and managing quiz
    @commands.dm_only()
    @commands.command("start_quiz", aliases=("start-quiz", "startquiz"))
    async def start_quiz(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        if len(self.quiz_channels) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> There is no quiz channel! Please contact an Administrator to "
                                   f"fix this issue.",
                                   delete_after=30)
            return

        if not self.bot_loaded:
            ControlWidget.quiz_channels = [self.bot.get_channel(chan).name for chan in self.quiz_channels]
            self.bot_loaded = True

        viewer = QuizViewer.get_viewer(ctx.author.id)
        if viewer:
            existing_quizzes = viewer.refresh()
            message = await ctx.author.dm_channel.fetch_message(viewer.message_id)
            embed, files = viewer.generate_viewer_embed()
            await message.edit(embed=embed)

            if 0 <= int(id) <= existing_quizzes:
                new_quiz = Quiz()
                new_quiz.construct_from_dict(QuizViewer.load_quiz_file(int(id)))
                new_control_widget = ControlWidget()
                new_control_widget.set_values(tracking_id=new_quiz.ID, owner=ctx.author.id)

                embed, files = new_control_widget.generate_widget_embed()
                private_message = await ctx.channel.send(embed=embed, files=files)
                new_control_widget.register(private_message.id)
                self.save_object(new_control_widget)
                self.save_object(new_quiz)
            else:
                await ctx.channel.send(f"<@{ctx.author.id}> There is no quiz with that ID!",
                                       delete_after=30)

        else:
            await ctx.channel.send(f"<@{ctx.author.id}> There is no viewer active! Please activate a quiz viewer using "
                                   f"**!view_quizzes** and try again. This is to avoid out-of-date quiz ID's.",
                                   delete_after=30)

    @commands.dm_only()
    @commands.command("select_channel", aliases=("select-channel", "selectchannel"))
    async def quiz_select_channel(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        widget = ControlWidget.get_widget(ctx.author.id)
        if widget:
            if widget.started:
                await ctx.channel.send(
                    f"<@{ctx.author.id}> The quiz already started!",
                    delete_after=30)
                return

            if 0 < int(id) <= len(self.quiz_channels):
                widget.started = True
                message = await ctx.author.dm_channel.fetch_message(widget.message_id)
                embed, files = widget.generate_widget_embed()
                await message.edit(embed=embed)
                for em in widget.control_emojis:
                    await message.add_reaction(em)

                quiz = Quiz.get_quiz(widget.tracking_id)
                quiz_channel = self.bot.get_channel(self.quiz_channels[int(id) - 1])
                embed, files = quiz.generate_quiz_embed()
                quiz_message = await quiz_channel.send(embed=embed, files=files)
                quiz.set_values(message_ids=[quiz_message.id],
                                channel_id=quiz_channel.id,
                                guild_id=quiz_channel.guild.id)
                react_message = quiz_message
                for i, em in enumerate(emoji_options[:len(quiz.options)]):
                    if i%20==0 and i > 0:
                        react_message = await quiz_channel.send("\u200b")
                        quiz.message_ids.append(react_message.id)
                    await react_message.add_reaction(em)
                self.save_object(widget)
                self.save_object(quiz)

            else:
                await ctx.channel.send(
                    f"<@{ctx.author.id}> That channel does not exist!",
                    delete_after=30)
        else:
            await ctx.channel.send(f"<@{ctx.author.id}> There is no widget active! Please activate a quiz viewer using "
                                   f"**!start_quiz** *<id>* and try again.",
                                   delete_after=30)

    @commands.dm_only()
    @commands.command("change_correct", aliases=("change-correct", "changecorrect"))
    async def change_correct_answer(self, ctx, id):
        if not id.isdigit():
            return
        if not self.admin_check(ctx):
            return

        widget = ControlWidget.get_widget(ctx.author.id)
        if widget:
            if widget.started:
                quiz = Quiz.get_quiz(widget.tracking_id)
                if 0 < int(id) <= len(quiz.options):
                    quiz.correct = int(id) - 1

                    embed, files = widget.generate_widget_embed()
                    message = await ctx.channel.fetch_message(widget.message_id)
                    await message.edit(embed=embed)
                    self.save_object(widget)
                    self.save_object(quiz)
            else:
                await ctx.channel.send(
                    f"<@{ctx.author.id}> The quiz is not yet active!",
                    delete_after=30)
        else:
            await ctx.channel.send(f"<@{ctx.author.id}> There is no widget active! Please activate a quiz viewer using "
                                   f"**!start_quiz** *<id>* and try again.",
                                   delete_after=30)

    # Admin management commands
    @commands.guild_only()
    @commands.command("mark_quiz_channel", aliases=("mark-quiz-channel","markquizchannel",
                                                    "mark_quizchannel", "mark-quizchannel"))
    async def mark_quiz_channel(self, ctx):
        if not self.admin_check(ctx):
            return
        self.quiz_channels.append(ctx.channel.id)
        self.save_channellist()
        ControlWidget.quiz_channels = [self.bot.get_channel(chan).name for chan in self.quiz_channels]
        await ctx.channel.send(f"<@{ctx.author.id}> Channel saved!",
                               delete_after=30)

    @commands.guild_only()
    @commands.command("unmark_quiz_channel", aliases=("unmark-quiz-channel", "unmarkquizchannel",
                                                      "unmark_quizchannel", "unmark-quizchannel"))
    async def unmark_quiz_channel(self, ctx):
        if not self.admin_check(ctx):
            return
        if ctx.channel.id in self.quiz_channels:
            self.quiz_channels.remove(ctx.channel.id)
            self.save_channellist()
            ControlWidget.quiz_channels = [self.bot.get_channel(chan).name for chan in self.quiz_channels]
            await ctx.channel.send(f"<@{ctx.author.id}> Channel removed!",
                                   delete_after=30)
