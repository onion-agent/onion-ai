# coding=utf-8
"""
@author B1lli
@date 12:52:49, 15 Dec 2024
@File:main.py
"""
import re
import json
import asyncio
import json_repair
import os
from openai import OpenAI,AsyncOpenAI
from flask import Flask, request, jsonify
from x import *

app = Flask(__name__)
loop = asyncio.get_event_loop()
API_KEY = os.getenv("API_KEY", "")
API_KEY_DEEPSEEK = os.getenv("API_KEY_DEEPSEEK", "")

# from llm_utils import *

'''LLM utils'''
async_client_deepseek = AsyncOpenAI(api_key=API_KEY_DEEPSEEK, base_url="https://api.deepseek.com/")
async_client = AsyncOpenAI(api_key=API_KEY)

async def deepseek_stream_chat_async(messages:list, model=None):
    if not model: model='deepseek-chat'
    response = await async_client_deepseek.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.5,
        stream=True
    )
    print('\nStart\n')
    response_result = []
    async for chunk in response:
        if chunk.choices:
            delta_str = chunk.choices[0].delta.content
            response_result.append(delta_str)
            if delta_str != "None":print(delta_str, end='')
    print('\nEnd\n')
    response_result = [i for i in response_result if i]
    response_result_str = ''.join(response_result)
    return response_result_str

async def openai_stream_chat_async(messages:list, model=None):
    if not model: model='gpt-4o-mini'
    response = await async_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.5,
        stream=True
    )
    print('\nStart\n')
    response_result = []
    async for chunk in response:
        if chunk.choices:
            delta_str = chunk.choices[0].delta.content
            response_result.append(delta_str)
            if delta_str != "None":print(delta_str, end='')
    print('\nEnd\n')
    response_result = [i for i in response_result if i]
    response_result_str = ''.join(response_result)
    return response_result_str


def remove_none_wrapper(func):
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if isinstance(result, str):
            # Remove the None in the beginning and the end
            result = result.strip('None')
        return result
    return wrapper


# Asynchronous streaming output dialog method
@remove_none_wrapper
async def stream_chat_async(messages:list, type:str='claude', model=None,force_json=False):
    if type == 'deepseek':
        return await deepseek_stream_chat_async(messages, model=model)
    if type == 'openai':
        return await openai_stream_chat_async( messages, model=model )

def extract_json_from_text(text: str):
    try :
        a = json_repair.loads ( text )
        if type(a) is dict :
            return a
        elif type(a) is list and a is not []:
            return a[-1]
        else:
            return text
    except Exception as e:
        print(f'json_repair error:{e}')
        return text


# General - Method for generating dictionary answers for asynchronous request LLM
async def request_llm_dic_async(llm_msg_lst,type="openai",model="claude-3-5-sonnet-20241022", force_json=False,max_retries=3) :
    """
    Asynchronously request the Large Language Model (LLM) to output a JSON answer and try to parse the JSON inside the answer.
    If parsing succeeds, convert the JSON into a dictionary and return it; if parsing fails, retry it up to the specified number of times.

    Parameters:
    llm_msg_lst (list): List of chat messages sent to LLM.
    max_retries (int): Maximum number of retries, default is 3.

    Returns:
    evaluation_res_dic (dict): The JSON dictionary after successful parsing, or an empty dictionary if all attempts fail.
    """
    evaluation_res_dic = {}
    for i in range ( max_retries ) :
        evaluation_res_raw = await stream_chat_async ( llm_msg_lst,type="openai",model="claude-3-5-sonnet-20241022",force_json=force_json )
        evaluation_res_dic = extract_json_from_text ( evaluation_res_raw )
        if not evaluation_res_dic :
            print ( f'Parsing JSON from LLM output failed, attempt {i + 1}' )
        else :
            break  # If the evaluated JSON result can be generated correctly, no retries will be made, otherwise an empty dictionary will be returned.

    return evaluation_res_dic

'''Engineering utils'''
import os
from datetime import datetime

def cache_news_text(news_text, log_filename='news_cache.log'):
    """
    Save the generated news text together with the timestamp into the log file in the current directory.

    parameter:
    news_text (str): Generated news text.
    log_filename (str): Log file name, default is 'news_cache.log'。
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(os.path.join(os.getcwd(), log_filename), 'a', encoding='utf-8') as log_file:
            log_file.write(f"[{timestamp}] {news_text}\n\n\n\n")
        print(f"The news text has been successfully written {log_filename}")
    except Exception as e:
        print(f"Error while writing log file: {e}")


'''Extract multiple related subjects from hot topics'''
async def extract_entity_from_topic(topic):
    message_list = []

    system_prompt = '''# Role: Association Subject Generation Assistant

## Description: This assistant is used to analyze the input current events, split the words in the event, and generate a dictionary of associated subjects for each word.

## Rules
1. The input text should contain a title and may contain detailed content.
2. The title needs to be broken down into words, and each word needs to be analyzed in detail.
3. The generated dictionary should contain the original text of the words, their parts of speech (POS), and the associated entities.
4. The associated entities should be as detailed as possible and relevant to the context of the words.

## Workflows
1. Identify and segment keywords and entities in input text.
2. Determine the part of speech (POS) of each word.
3. Generate a dictionary of associated entities for each term, including related entities and their relationships.
4. Outputs structured JSON results.

## Example
- Enter text：
    ```
    Trump was assassinated during a speech
    ```
- Desired result:
    ```json
    {
        "original_text": "Trump was assassinated during a speech",
        "analysis": [
            {
                "original_text":"Trump",
                "POS":"Noun",
                "related_entity": {
                    "Trump himself" : ["Trump"]
                }
            },
            {
                "original_text":"During the speech",
                "keyword":"speech",
                "POS":"Verb",
                "related_entity": {
                    "Sponsor of the speech":["U.S. Congress","Republican Party of the United States"],
                    "Speaker":["Trump"],
                    "Speech security": ["U.S. Secret Service"]
                }
            },
            {
                "original_text" : "Assassination",
                "POS" : "Verb",
                "related_entity" : {
                    "Assassination":["Killer"],
                    "The assassin":["Trump"],
                }
            },
        ]
    }
    ```
'''
    system_message = {"role" : "system", "content" : [{"type" : "text", "text" : system_prompt}]}
    message_list.append(system_message)

    user_prompt = f'Here are the hot topics you’ll want to analyze:\n"{topic}"\n Please output the analysis results of the associated subject in structured JSON format as required'
    user_prompt += '''- Desired result format:
```json
{
    "original_text": "Trump was assassinated during a speech",
    "analysis": [
        {
            "original_text":"Trump",
            "POS":"Noun",
            "related_entity": {
                "Trump himself" : ["Trump"]
            }
        },
        {
            "original_text":"During the speech",
            "keyword":"speech",
            "POS":"Verb",
            "related_entity": {
                "Sponsor of the speech":["U.S. Congress","Republican Party of the United States"],
                "Speaker":["Trump"],
                "Speech security": ["U.S. Secret Service"]
            }
        },
        {
            "original_text" : "Assassination",
            "POS" : "Verb",
            "related_entity" : {
                "Assassination":["Killer"],
                "The assassin":["Trump"],
            }
        },
    ]
}
```'''
    user_message = {"role" : "user", "content" : [{"type" : "text", "text" : user_prompt}]}
    message_list.append(user_message)

    res = await request_llm_dic_async(message_list,type="openai",model="claude-3-5-sonnet-20241022")

    return res


'''For each subject, point out the shortcomings of this subject'''
# Engineering Split the associated subject into multiple subjects
def split_related_entity_dic(related_entity_dic=None) :
    if not related_entity_dic: related_entity_dic = {
        "original_text" : "Trump was assassinated during a speech",
        "analysis" : [
            {
                "original_text" : "Trump",
                "POS" : "Noun",
                "related_entity" : {
                    "Trump himself" : ["Trump"]
                }
            },
            {
                "original_text" : "During the speech",
                "keyword" : "speech",
                "POS" : "Verb",
                "related_entity" : {
                    "Sponsor of the speech" : ["U.S. Congress","Republican Party of the United States"],
                    "Speaker" : ["Trump"],
                    "Speech security": ["U.S. Secret Service"]
                }
            },
            {
                "original_text" : "Assassination",
                "POS" : "Verb",
                "related_entity" : {
                    "Assassination Executor": ["Killer"],
                    "assassinated person": ["Trump"],
                }
            },
        ]
    }
    res_dic = []

    # Traverse each project in analysis
    for analysis_item in related_entity_dic["analysis"] :
        # Get the related_entity dictionary
        related_entity = analysis_item["related_entity"]

        # Iterate over each key-value pair in related_entity
        for relationship, entity_list in related_entity.items () :
            # Make sure the entity list is of type list
            if not isinstance ( entity_list, list ) :
                entity_list = [entity_list]

            # Create a new dictionary for each entity and add it to the result list
            for entity in entity_list :
                res_dic.append ( {relationship : entity} )

    return res_dic

# Extract the shortcomings of this subject
async def extract_flaws_from_entity(entity):
    message_list = []

    system_prompt = '''# Role: Senior politician'''
    system_message = {"role" : "system", "content" : [{"type" : "text", "text" : system_prompt}]}
    message_list.append ( system_message )

    user_prompt = f'{entity}What are some of the flaws that are worth being satirized?'
    user_message = {"role" : "user", "content" : [{"type" : "text", "text" : user_prompt}]}
    message_list.append ( user_message )

    # flaws_text = await stream_chat_async( message_list, type="openai", model="claude-3-5-sonnet-20241022" )
    flaws_text = await stream_chat_async( message_list, type="deepseek", model="deepseek-chat" )
    assistant_message = {"role" : "assistant", "content" : flaws_text.replace('None','')}
    message_list.append ( assistant_message )

    user_prpmpt_jsonify = 'Sort the above flaws into a json list and returned to me, as follows{"flaws":["xxx","xxx",..]}'
    user_message_jsonify = {"role" : "user", "content" : [{"type" : "text", "text" : user_prpmpt_jsonify}]}
    message_list.append ( user_message_jsonify )

    # flaws_dict = await request_llm_dic_async ( message_list, type="openai", model="claude-3-5-sonnet-20241022" )
    flaws_dict = await request_llm_dic_async ( message_list, type="deepseek", model="deepseek-chat" )

    return flaws_dict

# batch extraction of flaws of entimultiple entities
async def extract_flaws_for_entities_async(multi_entity_list):
    """parallel batch extraction in of flaws of entimultiple entities"""
    tasks = []
    for entity_dict in multi_entity_list:
        # Get the first value in the dictionary as an entity
        entity = list(entity_dict.values())[0]
        # Creating an asynchronous task
        task = extract_flaws_from_entity(entity)
        tasks.append(task)
    
    # Execute all tasks in parallel
    flaws_dicts = await asyncio.gather(*tasks)
    
    # Add the flaw dictionary to the corresponding entity dictionary
    for entity_dict, flaws_dict in zip(multi_entity_list, flaws_dicts):
        if flaws_dict:
            entity_dict['flaws'] = flaws_dict.get('flaws', [])
    
    return multi_entity_list


'''Generate Onion News'''
# Directly generate a single Onion News
async def generate_single_news_directly(topic, entity, flaw,type="deepseek",model="deepseek-chat"):
    """Directly generate Onion News"""
    message_list = []

    system_prompt = '''# Role: The Onion Writer's Assistant

## Description: Helps users generate satirical news articles that meet Associated Press specifications and mimic the style of The Onion.

## Skills
1. Ability to write satirical and humorous news articles.
2. Familiar with AP news writing style and format.
3. Ability to creatively transform real events or topics into satirical news.

## Rules
1. News articles must maintain a satirical and humorous tone.
2. The article structure should conform to the Associated Press news format, including title, lead, body, etc.
3. The content must be fictional, but based on real events or topics to enhance the satirical effect.

## Workflows
1. Decide on a topic or event to satirize.
2. Create an engaging and satirical headline.
3. Write an introduction that outlines the main point of the satire.
4. Write the body of the article, detailing the satire and ensuring it complies with the Associated Press format.
5. Edit and proofread to ensure the language is humorous and meets journalistic standards.
'''
    system_message = {"role": "system", "content": [{"type": "text", "text": system_prompt}]}
    message_list.append(system_message)

    assistant_prompt = '''The Onion is a satirical journalism that lampoons real-world events and trends, often through exaggeration and absurdity. Here are some possible types of news stories:

1. **Government policy**: Report ridiculous government decrees or policies, such as "The government announced that one day a week must be free of electronic devices."

2. **Scientific discovery**: Publish some exaggerated or impossible scientific research results, such as "Scientists have found that eating chocolate every day can make people immortal."

3. **Celebrity dynamics**: Report absurd behaviors or statements of celebrities, such as "A star announced that he would only wear clothes made of edible materials."

4. **Social trends**: Describe exaggerated social trends, such as "Young people are beginning to use ancient ways of communication, such as pigeons."

5. **Corporate news**: Report absurd decisions or new product launches of companies, such as "A company launched a refrigerator that can automatically eat."

6. **Education reform**: Describe absurd reforms in schools or education systems, such as "The school decided to use video games instead of traditional classroom teaching."

7. **International events**: Report absurd international events or diplomatic policies, such as "A country decided to use paper airplanes to deliver diplomatic letters."

8. **Health Advice**: Publishing unrealistic health advice, such as "eating five burgers a day will help you lose weight."

9. **Technological Development**: Describing impossible technological innovations, such as "a technology company released a smartphone that can predict the future."

10. **Cultural Events**: Reporting absurd cultural or artistic events, such as "a music festival was held where only people were allowed to walk backwards."

These types of news use humor and satire to provoke readers to think about real-world issues. '''
    assistant_message = {"role": "user" if type == "deepseek" else "assistant", "content": [{"type": "text", "text": assistant_prompt}]}
    message_list.append(assistant_message)

    user_prompt = f'''Recently, the following hot events have occurred: "{topic}"
Please try to use this incident as an excuse to satirize the flaw of "{entity}": "{flaw}"
Generate an Onion News
You only need to output the Onion News itself, without any explanatory text
The format for outputting onion news is as follows:
```
#Title
**Location * * - Text
```'''
    
    user_message = {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
    message_list.append(user_message)

    news_text = await stream_chat_async(message_list, type=type, model=model)

    cached_news_text = f'''
    Hot events: {topic}
    Satire target:{entity}
    Flaw description: {flaw}
    Selected model: {model}
    News content: {news_text}'''
    cache_news_text ( cached_news_text )
    
    return news_text

# Generate onion news in batches and in parallel
async def batch_generate_news_async(topics, entities_flaws_list):
    """Batch parallel generation of Onion News"""
    # Ensure `topics` is a list, even if it's a single string
    if isinstance(topics, str):
        topics = [topics]

    # This helper function generates news for a single topic and list of entity flaws
    async def generate_news_for_single_case(topic, entity_flaws):
        news_per_entity = []
        for entity_dict in entity_flaws:
            entity_name = list(entity_dict.keys())[0]
            entity_value = entity_dict[entity_name]
            random_flaw = random.choice(entity_dict['flaws'])  # Randomly choose a flaw
            news = await generate_single_news_directly(topic, entity_value, random_flaw)
            news_per_entity.append(news)
        return news_per_entity

    # Use asyncio.gather to asynchronously generate news for each topic
    tasks = [
        generate_news_for_single_case(topic, entities_flaws)
        for [topic], entities_flaws in zip(topics, entities_flaws_list)
    ]
    
    results = await asyncio.gather(*tasks)
    
    return results

async def generate_long_news_from_topic_and_entities(topic, multi_entity_flaws_list):
    import random

    # Randomly select a subject and its flaws
    random_entity_dict = random.choice ( multi_entity_flaws_list )
    entity_name = list ( random_entity_dict.keys () )[0]  # Get the subject name
    entity_value = random_entity_dict[entity_name]  # Get the specific value of the subject
    random_flaw = random.choice ( random_entity_dict['flaws'] )  # Randomly select a flaw

    # Generate a single Onion News article
    news = await generate_single_news_directly ( topic, entity_value, random_flaw,
                                                 type="openai",model="claude-3-5-sonnet-20241022"
                                                 )
    return news

'''提取出短洋葱新闻'''
async def extract_short_onion_news(oni_news,words_limit=100):
    message_list = []

    system_prompt = f'''For the following onion news, without changing the original text content, reduce specific paragraphs to a total text length of no more than {words_limit} words. Include the text in double "```" and output no more text.'''
    system_message = {"role" : "system", "content" : [{"type" : "text", "text" : system_prompt}]}
    message_list.append(system_message)

    user_prompt = f'{oni_news}'
    user_message = {"role" : "user", "content" : [{"type" : "text", "text" : user_prompt}]}
    message_list.append(user_message)

    res = await stream_chat_async(message_list,type="openai",model="claude-3-5-sonnet-20241022")

    cache_news_text(f"短洋葱新闻：\n{res}\n\n\n")
    return res

'''Test code'''
# Generate a single Onion News article based on a flaw of an entity
async def test_generate_onion_news(topic,multi_entity_flaws_list):
    if not topic:topic = "Trump was assassinated during his speech to Congress"
    if not multi_entity_flaws_list:multi_entity_flaws_list = [ {'Trump himself' : 'Donald Trump', 'flaws' : ['The speech is inconsistent, and lacking credibility.', 
    'Over-reliance on Twitter to publish opinions has caused market turmoil and international disputes', 'Lack of political experience and insufficient decision-making ability', 'Family businesses are intertwined with government affairs, resulting in serious conflicts of interest', 'Frequent attacks on the media, suppression of dissent, and threats to freedom of speech', 'Ignoring scientific advice and expert opinions led to the epidemic getting out of control', 'Racist speech and policies', 'Abuse of presidential power many times, faced impeachment']}, {'Trump himself' : 'Former US President', 'flaws' : ['Bush launched the Iraq War based on false intelligence, causing regional unrest', 'Bush and Obama favored Wall Street and ignored the public during the 2008 financial crisis', 'Nixon Watergate Scandal Exposed Government Corruption and Abuse of Power', 'Clinton-Lewinsky scandal damages president\'s reputation', 'Trump\'s zero-tolerance immigration policy leads to family separations', 'Obama\'s drone policy caused massive civilian casualties', 'Trump withdraws from Paris climate agreement, ignoring environmental responsibilities', 'Bush weakens environmental laws, harming public health', 'Reagan\'s trickle-down economics widens wealth inequality', 'Trump\'s tax cuts mainly benefit the rich and increase the deficit', 'Carter\'s human rights diplomacy is too idealistic to cope with crises', 'Obama\'s indecision during the Arab Spring led to unrest']}, {'Trump-related organizations' : 'Trump Organization', 'flaws' : ['Financial opacity, multiple allegations of tax fraud and false reporting of assets', 'Refusing to release tax returns, a violation of presidential practice', 'Serious business conflicts of interest during the presidency', 'Accepting improper benefits from foreign governments through hotel business', 'Faced numerous commercial fraud charges and contract breach disputes', 'Weak awareness of environmental protection, many projects damage the ecology', 'Inadequate protection of labor rights, low wages and poor working conditions', 'Serious nepotism, appointing inexperienced family members to key positions', 'Using the presidency to advance business interests for the family business', 'The brand image has been severely damaged by political controversy', 
    'Business decisions are overly politicized and deviate from normal business logic', 'Facing numerous legal actions and criminal investigations', 'under investigation for bank fraud and obstruction of justice', 
    'Enterprise management is chaotic and lacks effective internal supervision mechanism']}, {'Trump-related organizations' : 'Republican Party', 
    'flaws' : ['Extreme conservatism, rigid stance on social issues, denial of climate change', 'Short-sighted economic policies, over-emphasizing tax cuts and neglecting social welfare', 
    'Partisan loyalty takes precedence over national interests, and filibustering is frequently used', 'Discrimination on race and immigration issues, and implementation of strict immigration policies',
"Hostile to mainstream media, attacking press freedom, and spreading 'fake news'", 'Corruption and conflict of interest, double standards in ethics', 'Promoting legislation to restrict voting rights, threatening election fairness', 'Attempting to interfere with judicial independence and weaken the fairness of the judicial system',
'Inadequate protection of minority rights and interests, exacerbating social divisions', 'Backsliding on environmental issues, hindering climate governance', 'Fiscal policies favor the interests of the rich, exacerbating the gap between the rich and the poor', 'Skeptical of science and professional opinions, advocating populism']},
{'Speech venue' : 'U.S. Capitol', 'flaws' : [ 'Partisan confrontation and political polarization lead to inefficient legislation and failure of democratic decision-making mechanisms', 'Money politics prevails, and congressmen\'s decisions are influenced by big companies and wealthy people rather than public opinion',
'Legislative efficiency is extremely low, and important bills are often shelved or delayed due to party disputes', 'Lobbying groups overly influence the legislative process, causing policies to deviate from the public interest', 'The electoral system has serious flaws such as unfair districting and opaque funding',
'Members of the Legislative Council frequently have moral and ethical issues, such as sex scandals, corruption, and abuse of power', 'Insufficient attention is paid to the rights of minority groups, and social equality issues have not been resolved for a long time', 'Foreign policy is contradictory and chaotic, often causing tensions in international relations',
'Slow action in addressing major environmental issues such as climate change', 'Insufficient investment in social welfare, medical care, education and other livelihood issues']}, {'Speech venue' : 'House of Representatives meeting hall',
'flaws' : ['Partisan opposition and extremism: Members of the Legislative Council are more concerned with defeating the other side than solving problems, resulting in a slow legislative process', 'Money politics: decisions are influenced by big donors and special interest groups rather than the interests of voters',
'Abuse of rules of procedure: rules are used to delay or prevent legislation rather than promote debate and consensus', 'Hypocritical moral standards: lawmakers show double standards on moral issues', 'Formalism and bureaucracy: Overly cumbersome procedures and rituals affect the discussion of substantive issues',
'Loss of public trust: The disconnect between the political system and ordinary people leads to a crisis of trust', 'Arrogance of power: lawmakers show a superior attitude and ignore the opinions and needs of voters']}, {'Organizer' : 'US Congress',
'flaws' : ['Partisan opposition is serious, and lawmakers prioritize party interests rather than national interests', 'Money politics is prevalent, and lawmakers are easily influenced by big companies and special interest groups', 'Legislative efficiency is low, and complicated and lengthy procedures often delay important bills',
'Gerrymandering undermines the fairness of elections', 'Frequent moral problems among lawmakers, such as corruption and sex scandals', 'Over-focus on short-term political interests and neglect of long-term national development', 'The decision-making process lacks transparency, and it is difficult for the public to understand the true intentions']},
{'Organizer' : 'Republican Party', 'flaws' : ['Extreme conservatism hinders social progress and diversified development', 'Close ties with big companies and the wealthy, strong money politics', 'Denying the scientific consensus on climate change, irresponsible environmental protection stance',
'Too conservative on social issues such as LGBTQ+ rights and abortion', 'Double standards on election integrity, undermining the democratic system', 'Too tough foreign policy, prone to international conflicts', 'Serious internal factional struggles, affecting policy implementation']},
{'Speaker' : 'Trump', 'flaws' : ['Pursuing controversial policies such as the Muslim ban and withdrawing from the Paris Climate Agreement', 'Frequently using insulting language to belittle women, minorities and other countries', 'Lack of political experience, impulsive and poorly thought-out decision-making',
'Overly dependent on Twitter to express personal opinions, unstable and unpredictable speech', 'There is a family conflict of interest, and his daughter and son-in-law serve as senior White House advisers', 'Suspected of interfering with the judiciary and trying to influence the FBI\'s investigation into the Russia-Russia scandal',
'Poor response to the epidemic, denying the severity of the epidemic and recommending unproven treatments']}, {'audience' : 'Congressmen', 'flaws' : ['Overemphasis on party positions, obstructing bills that benefit the country for party interests',
'Influenced by special interest groups, becoming a spokesperson for financial sponsors rather than a representative of public opinion', 'Lack of substantive legislative achievements, keen on political performance and empty speeches', 'Stuck in red tape and bureaucracy, inefficient',
'Involved in moral issues such as corruption and sex scandals, inconsistent in words and deeds', 'Ignoring grassroots public opinion, overly concerned with national issues and elite interests', 'Overly concerned with re-election, legislating to please voters rather than national interests',
'Lack of transparency in operations, imperfect accountability mechanisms', 'Focusing on short-term interests and ignoring long-term national development', 'Lack of cross-party cooperation and undermining each other']},
{'audience' : 'Government officials', 'flaws' : [ 'Formalism and bureaucracy: excessive emphasis on form and procedure, ignoring practical problem solving', 'Rent-seeking and corruption: using power for personal gain and trading power for money',
'Information opacity and concealment of the truth: choosing to conceal or release false information in the face of doubts', 'Lazy politics and inaction: shirking and delaying in the face of problems, unwilling to take responsibility', 'Interest groups and nepotism: colluding with specific interest groups to form an interest community',
'Image projects and political achievement projects: pursuing short-term political achievements and ignoring long-term social benefits', 'Moral deviance and inconsistency between words and deeds: publicly promoting morality in a high-profile manner, and misbehaving in private', 'Excessive intervention and market distortion: excessive intervention in the market economy, resulting in ineffective resource allocation']},
{'Audience' : 'Special guests', 'flaws' : ['Excessive self-promotion, treating the platform as a personal show', 'The speech is empty and lacks substantive content, and is only for show', 'Overly catering to the audience, lack of independent thinking and opinions', 'Interrupting others and lack of respect for different opinions',
'Exaggerating facts or words to attract attention', 'Making irresponsible remarks on sensitive topics', 'Overly relying on team-prepared speeches', 'Commenting on a shallow understanding of professional knowledge']}, {'Security responsible party' : 'U.S. Secret Service',
'flaws' : ['Agents frequently exposed to alcoholism, sex scandals and other lax discipline', 'The lack of transparency in the operation of the agency easily leads to questions of abuse of power', 'Protection resources are unevenly distributed, overprotecting some politicians and ignoring others',
'Budget use is inefficient, travel protection expenses are extravagant and wasteful', 'There is a tendency to interfere in politics and it is difficult to maintain a neutral position', 'There are double standards for the protection of different politicians', 'Backward technical equipment and modernization level', 'Inadequate agent training standards and quality',
'Multiple scandals have led to a continuous decline in public trust', 'Excessive secrecy and lack of effective communication with the public', 'Over-reliance on traditional security measures', 'Insufficient ability to respond to new threats (such as cyber attacks and drones)']}, {'Security responsible party' : 'Capitol Police',
'flaws' : ['Excessive use of force, which easily arouses public doubts when dealing with protests and demonstrations', 'Lack of transparency and accountability, and the decision-making process is not open enough', 'There are cultural problems such as racial discrimination and gender discrimination within the organization', 'Uneven resource allocation leads to an imbalance in the allocation of security forces',
'Inadequate ability to respond to emergencies, especially during large-scale protests', 'Poor communication with the public, which easily leads to misunderstanding and distrust', 'There is a tendency to politicize, which may undermine independence and credibility']}, {'Security responsible party' : 'Washington, D.C. Police Department',
'flaws' : ['As the capital\'s police, it frequently uses excessive force, which is an ironic contrast to the democracy and human rights advocated by the United States', 'There is obvious racial discrimination in law enforcement, which is contrary to the concept of equality and justice advocated by the government',
'Internal corruption and chaotic management form a sharp contrast with its status as a benchmark for the capital\'s law enforcement agencies', 'Too close to political power, it has lost the independence that a neutral law enforcement agency should have', 'Excessive enforcement of laws against low-income communities runs counter to the image of the capital\'s diversity and inclusion',
'Lack of effective transparency and accountability mechanisms, and a non-existent supervision system', 'Ignoring the professional treatment of mental health issues and over-relying on coercive law enforcement']}, {'Potential victims' : 'Trump', 'flaws' : ['Withdrawing from important international agreements and undermining global cooperation',
"Frequently using 'fake news' to attack the media and making a large number of unverified statements", 'Autocratic leadership style leads to chaos within the government', 'Inappropriate words and deeds in public, undermining the dignity of the president', 'Refusing to release tax returns, financial transparency is questionable',
'Refusing to admit defeat in 2020, undermining the democratic system']}, {'Law enforcement agencies' : 'Federal Bureau of Investigation (FBI)', 'flaws' : ['Excessive expansion of power, covering almost everything from counterterrorism to counterintelligence to ordinary criminal cases, seriously eroding civil liberties',
'Abuse of surveillance technology, such as Stingray devices, excessive monitoring of ordinary citizens rather than real criminals', 'Double standards for different political factions and social groups, such as the different attitudes towards the investigation of Hillary and Trump teams during the 2016 election',
'Frequent internal corruption and mismanagement, such as former Director Comey\'s controversial behavior in the email gate incident', 'Over-reliance on informants, who may provide false intelligence in order to reduce sentences or for money',
'Obvious bias and discrimination against minorities, such as the COINTELPRO program\'s surveillance of civil rights leaders', 'Frequent information leaks and transparency issues, such as the loopholes exposed in the Snowden incident and WikiLeaks incident',
'Law enforcement is overly politicized and often seen as a tool for partisan struggle', 'Serious violation of citizens\' privacy rights on the grounds of national security, such as frequent requests for technology companies to provide encrypted data backdoors', 'Ineffective response to foreign interference, such as the slow response to Russia\'s interference in the 2016 election']},
{'Law enforcement' : 'US Secret Service', 'flaws' : ['Agents have disciplinary problems such as drinking and sex scandals while on duty', 'Agents are not well trained and lack the ability to deal with complex threats', 'Resources are overly concentrated on protecting the president, ignoring the safety of other important people',
'Budget limitations limit equipment updates and personnel expansion', 'Work is overly confidential, lacks transparency and effective accountability mechanisms', 'Senior leaders are influenced by political appointments and have partisan tendencies', 'Equipment and technology are relatively backward, and the ability to deal with modern threats is insufficient',
'Lack of innovation and slow response to new threats', 'Over-reliance on manpower rather than technical means, prone to human errors', 'Frequent internal scandals have led to a decline in public trust', 'Internal management is loose and discipline is not strictly enforced', 'Prevention and emergency mechanisms are imperfect']},
{'Law enforcement' : 'Department of Homeland Security', 'flaws' : ['Bureaucracy leads to slow decision-making and inefficiency', 'Inter-departmental coordination is difficult and resources are wasted repeatedly', 'Over-reliance on high-tech equipment and neglect of humane management',
'Ignoring humanitarian principles when dealing with immigration issues', 'Over-centralization of power and expanding scope of intervention', 'Large-scale surveillance projects infringe on citizens\' privacy rights', 'Inefficient use of funds and a lot of waste', 'Internal corruption is difficult to effectively curb',
'Double standards and discrimination in law enforcement', 'Policy making is overly influenced by political factors', 'Inadequate preparation for natural disasters and delayed response', 'Unbalanced distribution of disaster relief resources']}, {'Parties involved' : 'Assassin/suspect',
'flaws' : ['Extreme idealism: claiming to fight for lofty ideals, but relying on violent destruction', 'Egocentric heroism: seeing oneself as a savior, but only bringing chaos and pain', 'Lack of empathy: turning a blind eye to the suffering of victims and thinking they are justified',
'Short-sighted strategy: believing that violence can quickly solve problems, but in fact it causes more conflicts', 'Double standards of morality: strict requirements for others, tolerance and indulgence for oneself', 'Desire for power: under the banner of serving the people, it is actually a desire for personal power',
'Ignorance of history: ignoring historical lessons and blindly believing that they are unique', 'Contempt for the law: using the excuse of legal injustice to ignore the spirit of the rule of law']}, {'Related parties' : 'Eyewitnesses',
'flaws' : [ 'Unreliability of memory: human memory is easily affected by subsequent information and emotions, often leading to distorted testimony', 'Confirmation bias: witnesses tend to remember information that meets their expectations and ignore details that do not meet their expectations', 'Visual illusion: The human visual system is prone to misjudgment in complex or stressful situations', 'Post-event information interference: External information such as media reports can affect and reshape witnesses\' memories',
 'Stress and emotional influence: Emotions such as tension and fear can cause details to be omitted or exaggerated',
'Racial and gender bias: Social stereotypes can affect witnesses\' descriptions of suspects', 'Overconfidence: Witnesses are overconfident in their own memory judgments, even if they are inconsistent with the facts', 'Social pressure and herd mentality: Group witnesses are easily influenced by others to change their testimonies',
'Language expression limitations: It is difficult to accurately describe complex or rapidly changing scenes in words', 'Ethical and legal conflicts: Social pressure may provide testimony that conforms to expectations rather than facts']}, {'Related parties' : 'Emergency medical personnel',
'flaws' : ['Uneven distribution of resources, abundant resources in wealthy areas and scarce resources in remote areas', 'Over-reliance on high-tech equipment and neglect of basic first aid skills', 'Red tape and bureaucracy delay rescue time', 'Insufficient training leads to skill degradation and rustiness',
'Mental health issues in long-term high-pressure work environments are ignored', 'There is a huge gap between public expectations and actual capabilities', 'Excessive commercialization affects the quality and fairness of medical services', 'Lack of effective cooperation mechanisms with fire, police and other departments']},
{'Investigation agency' : 'Ministry of Justice', 'flaws' : ['Concentration of power and insufficient supervision easily lead to abuse of power and political interference', 'Serious bureaucracy and inefficient case handling', 'Uneven distribution of judicial resources and excessive burden on grassroots',
'Lack of transparency in decision-making process and internal operations', 'Staff quality varies and professional ability is insufficient', 'Conflict of interest and corruption exist', 'Inconsistent legal application standards and inconsistent law enforcement standards', 'Lack of public participation and disconnection between decision-making process and public opinion',
'Lagged behind in information construction and inefficient case management', 'Insufficient international judicial cooperation and inefficient handling of transnational cases']}, {'Investigation agency' : 'FBI',
'flaws' : ['Excessive political interference, showing obvious double standards and bias in key elections', 'Abuse of surveillance power, frequent sting enforcement, and violation of citizens\' privacy rights',
'Serious internal corruption, lack of transparency and accountability mechanism for senior leaders', 'Over-reliance on technical means for law enforcement, leading to misjudgments and false convictions', 'Slow response to foreign interference in US internal affairs, failure to take effective measures in a timely manner',
'Systematic bias and discrimination against ethnic minorities', 'Excessive confidentiality of information, refusal to disclose important historical case files', 'Suppression of dissidents and journalists, threatening freedom of speech and freedom of the press', 'Internal management is chaotic, and corruption cases of agents are frequent',
"Abuse of legal tools such as 'National Security Letters' to obtain communication data"]}, {'Investigation Agency' : 'District Attorney\'s Office', 'flaws' : ['Excessive pursuit of conviction rate, ignoring the substantive justice of the case', 'Position election leads to politicization, and there is selective law enforcement',
'Uneven allocation of resources affects the quality of case handling', 'Imbalance in handling serious and minor crimes, biased law enforcement priorities', 'Lack of transparency and effective accountability mechanisms', 'Discrimination based on race and socioeconomic status', 'Over-reliance on plea agreements affects the rights of defendants',
'Ignoring the voices of victims and communities, and focusing too much on the legal aspect']}]
    import random

    # Randomly select a subject and its flaws
    random_entity_dict = random.choice ( multi_entity_flaws_list )
    entity_name = list ( random_entity_dict.keys () )[0]  # Get the subject name
    entity_value = random_entity_dict[entity_name]  # Get the specific value of the subject
    random_flaw = random.choice ( random_entity_dict['flaws'] )  # Randomly select a flaw

    # Generate a single Onion News article
    news = await generate_single_news_directly ( topic, entity_value, random_flaw,
                                                 type="openai",model="claude-3-5-sonnet-20241022"
                                                 )

    shrinked_news = await extract_short_onion_news(news,words_limit=100)

    return shrinked_news

async def generate_long_news_from_topic(topic):
    # Extract multiple related subjects from hot topics
    related_entity_dic = await extract_entity_from_topic(topic)

    # # For each subject, point out the flaws of this subject
    multi_entity_list = split_related_entity_dic(related_entity_dic)

    # # Extract all entities in parallel
    multi_entity_flaws_list = await extract_flaws_for_entities_async(multi_entity_list)
    # print(multi_entity_flaws_list)
    # Generate Onion News in batches and in parallel
    news = await generate_long_news_from_topic_and_entities(topic, multi_entity_flaws_list)

    return { "news": news, "multi_entity_flaws_list": multi_entity_flaws_list }


'''Main method'''
async def main():
    topic = "Trump was assassinated during his speech to Congress"

    # '''Extract multiple related subjects from hot topics'''
    # related_entity_dic = await extract_entity_from_topic(topic)
    #
    # '''For each subject, point out the flaws of this subject'''
    # multi_entity_list = split_related_entity_dic(related_entity_dic)
    #
    # '''extract all entities in parallel'''
    # # This step consumes a lot of tokens, so be sure to cache the results of this step so that you only need to run it again when changing topics to avoid repeated requests. Currently, I use Deepseek to reduce costs in this step.
    # multi_entity_flaws_list = await extract_flaws_for_entities(multi_entity_list)

    await generate_long_news_from_topic(topic)

@app.route('/api/send_twitter', methods=['POST'])
def send_twitter():
    body = request.get_json()
    title = body.get('title')
    content = body.get('content')
    slug = body.get('slug')
    result = create_tweet({
        "title": title,
        "content": content,
        "slug": slug
    })
    return jsonify({"status": "success", "data": result})

@app.route('/api/generate_and_send_twitter', methods=['POST'])
def generate_one():
    body = request.get_json()
    topic = body.get('topic')
    multi_entity_flaws_list = body.get('multi_entity_flaws_list')
    print(topic)
    print(multi_entity_flaws_list)
    news = loop.run_until_complete(test_generate_onion_news(topic, multi_entity_flaws_list))
    return jsonify({"status": "success", "data": news, "x_result": x_result})

@app.route('/api/generate_long_news_from_topic', methods=['POST'])
def generate_long_news_from_topic_api():
    body = request.get_json()
    topic = body.get('topic')
    news = loop.run_until_complete(generate_long_news_from_topic(topic))
    return jsonify({"status": "success", "data": news})

@app.route('/api/extract_entry', methods=['POST'])
def extract_entry_api():
    body = request.get_json()
    topic = body.get('topic')
    related_entity_dic = loop.run_until_complete(extract_entity_from_topic(topic))
    multi_entity_list = split_related_entity_dic(related_entity_dic)
    return jsonify({"status": "success", "data": {
        "related_entity_dic": related_entity_dic,
        "multi_entity_list": multi_entity_list
    } })

@app.route('/api/extract_flaws_from_entity', methods=['POST'])
def extract_flaws_from_entity_api():
    body = request.get_json()
    entity = body.get('entity')
    flaws_dict = loop.run_until_complete(extract_flaws_from_entity(entity))
    return jsonify({"status": "success", "data": flaws_dict})

@app.route('/api/extract_flaws_for_entities_async', methods=['POST'])
def extract_flaws_for_entities_api():
    body = request.get_json()
    multi_entity_list = body.get('multi_entity_list')
    multi_entity_flaws_list = loop.run_until_complete(extract_flaws_for_entities_async(multi_entity_list))
    return jsonify({"status": "success", "data": multi_entity_flaws_list})

@app.route('/api/generate_long_news_from_topic_and_entities', methods=['POST'])
def generate_long_news_from_topic_and_entities_api():
    body = request.get_json()
    topic = body.get('topic')
    multi_entity_flaws_list = body.get('multi_entity_flaws_list')
    news = loop.run_until_complete(generate_long_news_from_topic_and_entities(topic, multi_entity_flaws_list))
    return jsonify({"status": "success", "data": news})

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)
    # asyncio.run(generate_long_news_from_topic('A lynching in the family inspired Michigan\'s first Black woman elected justice to pursue the law'))
    '''The following is the test code'''
    # related_entity_dic = { "original_text": "Trump was assassinated during a speech", "analysis": [ { "original_text":"Trump", "POS":"Noun", "related_entity": { "Trump himself" : ["Trump"] } }, { "original_text":"During the speech", "keyword":"speech", "POS":"Verb", "related_entity": { "Sponsor of the speech": ["U.S. Congress", "U.S. Republican Party"], "Speaker": ["Trump"], "Speech security": ["U.S. Secret Service"]} }, 
    # { "original_text" : "assassination attempt", "POS" : "Verb", "related_entity" : { "assassination perpetrator": ["assassin"], "assassinated person": ["Trump"], } }, ] }
    # # Test split_related_entity_dic function
    # multi_entity_list = [{'Trump himself': 'Donald Trump'}, {'Trump himself': 'Former US President'}, {'Trump-related organizations': 'Trump Group'}, {'Trump-related organizations': 'Republican Party'},
 # {'Speech venue': 'U.S. Capitol'}, {'Speech venue': 'House of Representatives Chamber'}, {'Organizer': 'U.S. Congress'}, {'Organizer': 'Republican Party'}, {'Speaker': 'Trump'}, {'Audience': 'Congressmen'},
 #{'Audience': 'Government officials'}, {'Audience': 'Special guests'}, {'Security responsible party': 'U.S. Secret Service'}, {'Security responsible party': 'Capitol Police'}, {'Security responsible party': 'Washington, D.C. Police Department'}, {'Potential victims': 'Trump'},
 #{'Law enforcement agency': 'Federal Bureau of Investigation (FBI)'}, {'Law Enforcement': 'U.S. Secret Service'}, {'Law Enforcement': 'Department of Homeland Security'}, {'Party of Interest': 'Assassin/Suspect'}, {'Party of Interest': 'Witness'}, {'Party of Interest': 'Emergency Medical Personnel'},
 # {'Investigation Agency': 'Department of Justice'}, {'Investigation Agency': 'FBI'}, {'Investigation Agency': 'District Attorney's Office'}]
    # asyncio.run(extract_flaws_for_entities(multi_entity_list))