from flask import Flask, render_template, request, session, redirect, url_for
import requests, json, re
from functools import partial
from operator import is_not

app = Flask(__name__)
app.secret_key = "your_secret_key1"  # Replace with your strong secret key

OPENAI_API_KEY = "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"
BASE_MODEL = "ft:gpt-3.5-turbo-1106:filmassistantai::8qt8P4td"
DETAIL_MODEL = "ft:gpt-3.5-turbo-1106:filmassistantai::8RSuexIL"
SUMMARY_MODEL = "ft:gpt-3.5-turbo-0125:filmassistantai:supp-sum:8yOMaxyc"
API_URL = "https://api.openai.com/v1/chat/completions"

segments = ['M', 'T', 'CQ', 'G', 'S', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9']
delimiter =  '\n'

def parse_detail_level(detail_tag):
    return {
        '<detail-low>': '1',
        '<detail-medium>': '2',
        '<detail-high>': '3'
    }.get(detail_tag, '2')  # Default to 'medium' if tag is not found

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'new_session' not in session:
        session.clear()
        session['new_session'] = True
        session['outputs'] = {seg: '' for seg in segments}
        session['details'] = {seg: '2' for seg in segments if seg.startswith('S')}
    outputs = session['outputs']
    details = session.get('details', {seg: '2' for seg in segments if seg.startswith('S')})
    detail_mode_active = request.form.get("submit_detail_adjustments") == "True"
    generate_story = request.form.get("generate_story") == "True"
    enter_detail_control = request.form.get("enter_detail_mode") == "True"
    exit_detail_control = request.form.get("exit_detail_control") == "True"
    generate_summary = request.form.get("generate_summary") == "True"
    
    # initialize current mode
    # if in enter detail mode go back to html and grey out text boxes and enable detail level
    if "enter_detail_control" in request.form:
        enter_detail_control = True
    else:
        enter_detail_control = False
    # generate story
    if "generate_story" in request.form:
        generate_story = True
    else:
        generate_story = False
    # go back to 
    if "exit_detail_control" in request.form:
        exit_detail_control = True
    else:
        exit_detail_control = False
    # adjust detail level and resubmit     
    if "submit_detail_adjustments" in request.form:
        detail_mode_active = True
    else:
        detail_mode_active = False
    if "generate_summary" in request.form:
        generate_summary = True
    else:
        generate_summary = False    
    
    if request.method == 'POST':
        if "reset_session" in request.form:
            session.clear()
            return redirect(url_for('index'))

        user_inputs = {seg: request.form.get(seg) for seg in segments}
        print("User Inputs:", user_inputs)
           
        session['cached_outputs'] = outputs.copy()
       
        if "exit_detail_control" in request.form:
            detail_mode_active = False
            enter_detail_control = False
            # Additional code for processing the detail adjustments...
            print("Exiting Detail Mode.")

        # define messages 
        messages = []
        print("detail", detail_mode_active)
        print("generate_story", "generate_story" in request.form)
        outputs = session['outputs']
        
        if generate_summary:        
            print("GENERATE SUMMARY")
            # Construct messages for summary model
            supplementary_fields = ['M', 'T', 'G', 'CQ']
            summary_input = "\n".join([f"{seg}: {user_inputs[seg]}" for seg in supplementary_fields if user_inputs[seg]])
            messages.append({"role": "system", "content": "You are a storytelling AI. Create a cohesive, 3 sentence original story summary based on the provided supplementary fields. Mention at least one specific character and structure the output as follows: 'SUM: (Summary)'."})
            messages.append({"role": "user", "content": summary_input})
            
            print("Messages sent to the model:", messages)
            
            api_response = requests.post(
                API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                },
                json={
                    "model": SUMMARY_MODEL,
                    "messages": messages
                }
            )
            
            # Debugging prints
            print("API Response:", api_response.text)

            # Parse response
            response = api_response.json()
            assistant_output = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            print("Raw Assistant Output:", assistant_output)
            
            # Extract summary from assistant output
            if 'SUM:' in assistant_output:
                start_idx = assistant_output.find('SUM:') + len('SUM:')
                summary_output = assistant_output[start_idx:].strip()
            else:
                summary_output = assistant_output.strip()
            
            print("Parsed Summary Output:", summary_output)
            
            outputs['SUM'] = summary_output
            session['outputs'] = outputs
            
            # Redirect to generate story with the updated summary
            return redirect(url_for('index', generate_story=True))

        if detail_mode_active:
            # Construct messages for detail model
            print("in messageappend")
            messages.append({"role": "system", "content": "You are a screenwriting AI, adjust the details based on user inputs."})

            # Append detail level adjustments
            for seg in segments:
                if seg.startswith('S'):
                    detail_level = request.form.get(f"{seg}_detail", details[seg])
                    
                    if detail_level != details[seg]:
                        print("detail level", detail_level, "detailseg", details[seg])
                        adjusted_level = 'low' if detail_level == '1' else 'medium' if detail_level == '2' else 'high'
                        messages.append({"role": "user", "content": f"{seg} detail-{adjusted_level}"})
                        details[seg] = detail_level

            # Append cached output
            cached_output_text = "\n".join([f"{seg}: {session['cached_outputs'][seg]}" for seg in segments if session['cached_outputs'][seg]])
            messages.append({"role": "user", "content": cached_output_text})

        elif not detail_mode_active and "generate_story" in request.form:
            # Construct messages for base model
            print("in base if")
            story_input = "\n".join([f"{seg}: {user_inputs[seg]}" for seg in segments if user_inputs[seg]])
            messages.append({"role": "system", "content": "You are a storytelling AI. Create a story with a cohesive narrative arc based on the User's inputs. Include at least 3 unique characters and a specific, story driving event in each story segment. Structure the story as follows: M: (Mood) \nT: (Theme) \nCQ: (Core Question) \nG: (Genre) \nSUM: (Summary) \nS1:(Introduction and Stasis) \nS2: (Inciting Incident) \nS3: (Point of No Return) \nS4: (1st Pinch Point) \nS5: (Midpoint) \nS6: (2nd Pinch Point:) \nS7: (3rd Plot Point) \nS8: (Climax) \nS9 (Resolution). Ensure that the Core question introduced in the beginning is subtly interwoven through each segment, guiding character development and plot progression."})
            messages.append({"role": "user", "content": story_input})
        
        print("Messages sent to the model:", messages)
        
        # only call model if in generate mode or in detail active mode
        if generate_story or detail_mode_active:
            model = DETAIL_MODEL if detail_mode_active else BASE_MODEL
            print("Model being used:", model)
        
            # Send request to OpenAI API
            api_response = requests.post(
                API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                },
                json={
                    "model": model,
                    "messages": messages
                }
            )

            # Debugging prints
            print("API Response:", api_response.text)

            # Parse response
            response = api_response.json()
            assistant_output = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            print("Raw Assistant Output:", assistant_output)

        if generate_story or detail_mode_active:
            for segment in segments:
                prefix = f"{segment}:"
                if prefix in assistant_output:
                    start_idx = assistant_output.find(prefix) + len(prefix)
                    end_idx = assistant_output.find("\n", start_idx) if "\n" in assistant_output[start_idx:] else len(assistant_output)
                    segment_output = assistant_output[start_idx:end_idx].strip()

                    # Remove detail tags
                    if '<detail-' in segment_output:
                        segment_output = segment_output.split('>')[1] if '>' in segment_output else segment_output
                    outputs[segment] = segment_output
        
        session['outputs'] = outputs
        session['details'] = details
        
        return render_template('Claude-htmltest.html', outputs=outputs, details=details, enter_detail_control=enter_detail_control)
    
    return render_template('Claude-htmltest.html', outputs=outputs, details=details, enter_detail_control=enter_detail_control)

if __name__ == '__main__':
    app.run(debug=True, port=7000)