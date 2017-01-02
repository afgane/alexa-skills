"""An Amazon Alexa skill for Galaxy on the Cloud."""
from cloudbridge.cloud.factory import CloudProviderFactory, ProviderList
from flask import Flask
from flask_ask import Ask, statement, question, session
from time import localtime, strftime

app = Flask(__name__)
ask = Ask(app, "/")

help_text = ("You can say a name of the target cloud. Currently, only "
             "Jetstream cloud is available.")


def _get_jetstream_conn():
    os_username = os_project_name = "YOUR USERNAME"
    os_password = "YOUR PASSWORD"

    js_config = {"os_username": os_username,
                 "os_password": os_password,
                 "os_auth_url": "https://jblb.jetstream-cloud.org:35357/v3",
                 "os_user_domain_name": "tacc",
                 "os_project_domain_name": "tacc",
                 "os_project_name": os_project_name}
    return CloudProviderFactory().create_provider(ProviderList.OPENSTACK,
                                                  js_config)


def launch_instance(cloud):
    """Launch an instance, returning the instance object."""
    js = _get_jetstream_conn()

    sgs = ['CloudLaunchDefault']
    kp_name = "cloudman_key_pair"
    inst_size = 'm1.small'
    network_id = '86a1c3e8-b1fb-41f3-bcaf-8334567fe989'
    lc = js.compute.instances.create_launch_config()
    lc.add_network_interface(network_id)

    img_id = '2cf07e4a-62a8-41c2-9282-f3c53962f296'  # Gxy Standalone 161021b01
    name = 'ea-galaxy-{0}'.format(strftime("%m-%d-%H-%M", localtime()))

    i = js.compute.instances.create(
        name, img_id, inst_size, security_groups=sgs, launch_config=lc,
        key_pair=kp_name)
    return i


@ask.launch
def start_skill():
    """Skill entry point."""
    start_message = "Would you like to list instances or launch a new one?"
    return question(start_message)  # .reprompt(help_text)


@ask.intent("ListIntent")
def list_instances():
    """Fetch the list of currently available instances."""
    js = _get_jetstream_conn()
    il = js.compute.instances.list()
    if not il:
        msg = "You don't have any instances available."
    else:
        msg = ("You have {0} instances available. Here are up to 3 most "
               "recent: ".format(len(il)))
    msg_ex = ""
    content = ""
    for i in il[:3]:
        msg_ex += "{0},".format(i.name)
        content += "{0} ({1})\n".format(
            i.name, i.public_ips[0] if i.public_ips else i.private_ips[0])
    return statement(msg + msg_ex).simple_card(title=msg, content=content)


@ask.intent("LaunchIntent")
def launch_intent():
    """React to the user request to launch a new instance."""
    welcome_message = "On which cloud would you like to launch Galaxy?"
    return question(welcome_message).reprompt(help_text)


@ask.intent("JetstreamIntent")
def launch_on_jetstream():
    """Initiate an instance launch process (works for Jetstream only)."""
    launched = launch_instance("Jetstream")
    session.attributes['instance_id'] = launched.id
    session.attributes['public_ip'] = None
    session.attributes['status'] = None

    msg = "An instance is starting. Would you like to check its status?"
    return question(msg)


@ask.intent("YesIntent")
@ask.intent("InstanceStatusIntent")
def check_status():
    """Check on the status of the latest instance in session."""
    js = _get_jetstream_conn()
    i = js.compute.instances.get(session.attributes.get('instance_id'))
    if not i:
        return question("There was a problem. Please retry your command.")

    status = i.state
    if session.attributes['status'] != status:
        msg = "New instance status is {0}.".format(status)
        if not session.attributes['public_ip'] and status == 'running':
            # Attach a floating IP to the instance
            fip = None
            fips = js.network.floating_ips()
            for ip in fips:
                if not ip.in_use():
                    fip = ip
            if fip:
                i.add_floating_ip(fip.public_ip)
                session.attributes['public_ip'] = fip.public_ip
    else:
        msg = "Instance status is {0}".format(status)

    session.attributes['status'] = status

    if session.attributes['status'] != 'running':
        q = "Would you like to check the status again?"
        return question(msg + q).reprompt(q)
    else:
        card_content = 'Access your instance at http://{0}'.format(
            session.attributes.get('public_ip'))
        return statement(msg).simple_card(
            title="Instance {0} was launched.".format(i.name),
            content=msg + card_content)


@ask.intent("AMAZON.CancelIntent")
@ask.intent("AMAZON.StopIntent")
@ask.intent("AMAZON.NoIntent")
def no_intent():
    """Stop the skill."""
    bye_text = "OK"
    return statement(bye_text)


@ask.intent("AMAZON.HelpIntent")
def help():
    """Provide some contextual help for the skill."""
    return statement(help_text)

if __name__ == "__main__":
    app.run(debug=True)
