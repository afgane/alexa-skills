"""An Amazon Alexa skill for the Galaxy application."""
from bioblend.galaxy import GalaxyInstance
from datetime import datetime
from flask import Flask
from flask_ask import Ask, statement

app = Flask(__name__)
ask = Ask(app, '/')
gi = GalaxyInstance('https://usegalaxy.org/',
                    key='PUT YOUR API KEY HERE')


def get_jobs():
    """Get current Galaxy jobs."""
    jl = gi.jobs.get_jobs()
    running = [j for j in jl if j['state'] in ['running']]
    queued = [j for j in jl if j['state'] in ['queued', 'new']]
    return {'running': running, 'queued': queued}


def _hdiff(diff):
    """Humanize the timedelta diff object."""
    s = diff.seconds
    if diff.days == 1:
        return '1 day'
    elif diff.days > 1:
        return '{} days'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds'.format(s)
    elif s < 120:
        return '1 minute'
    elif s < 3600:
        return '{} minutes'.format(s / 60)
    elif s < 7200:
        return '1 hour'
    else:
        return '{} hours'.format(s / 3600)


def _get_jobs_info(jobs):
    """Iterate through jobs to extract desired info."""
    now = datetime.utcnow()
    info = []
    for job in jobs:
        active_time = now - datetime.strptime(job['update_time'],
                                              "%Y-%m-%dT%H:%M:%S.%f")
        tool_name = gi.tools.show_tool(job['tool_id']).get('name')
        info.append({'id': job['id'],
                     'active_time': active_time,
                     'tool_name': tool_name})
    return info


def _get_card_content(jobs):
    """Extract and format job info for user display."""
    content = ""
    if jobs['running']:
        running_info = _get_jobs_info(jobs['running'])
        for job in running_info:
            content += " - {0} running for {1}\n".format(
                job['tool_name'], _hdiff(job['active_time']))
    if jobs['queued']:
        qd_info = _get_jobs_info(jobs['queued'])
        content += "Queued jobs:\n"
        for job in qd_info:
            content += " - {0} queued for {1}\n".format(
                job['tool_name'], _hdiff(job['active_time']))
    # print(content)
    return content

print(_get_card_content(get_jobs()))


@ask.launch
def start_skill():
    """Run the skill."""
    jobs = get_jobs()
    running = jobs['running']
    queued = jobs['queued']

    total_num = len(running + queued)
    start_msg = "You currently have {0} jobs active".format(total_num)
    running_msg = ', {} running'.format(len(running))
    queued_msg = ', {} queued'.format(len(queued))

    if total_num > 1:
        if len(running) == total_num:
            jobs_msg = "You currently have {0} jobs running.".format(total_num)
        elif len(queued) == total_num:
            jobs_msg = "You currently have {0} jobs queued.".format(total_num)
        else:
            jobs_msg = start_msg
            if len(running) > 0:
                jobs_msg += running_msg
            if len(queued) > 0:
                jobs_msg += queued_msg

    elif total_num == 0:
        jobs_msg = "No jobs are currently running.".format(len(jobs))
    elif len(running) > 0:
        jobs_msg = "You have one job running."
    else:
        jobs_msg = "You have one job queued."

    return statement(jobs_msg).simple_card(
        title=jobs_msg,
        content=_get_card_content(jobs))


if __name__ == '__main__':
    app.run(debug=True)
