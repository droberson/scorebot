import json
import random
from datetime import datetime
from dateutil import tz

from django.db import models
from django.utils import timezone
from picklefield.fields import PickledObjectField

"""
    SBE Host Models

    Contains all Models that would be considered in game
"""


class Game(models.Model):
    GAME_MODES = {
        'RVB': 0,       # Standard Red vs Blue
        'BVB': 1,       # Blue vs Blue (Binjutisu)
        'KING': 2,      # King of the Box
        'RUSH': 3,      # Offense Time Trial
        'DEFEND': 4,    # Defense Time Trial
    }

    __desc__ = """
        SBE Game

        The Game object is a struct that holds all the data for a Scorebot game.
    """
    __historical__ = True

    class Meta:
        verbose_name = 'SBE Game'
        verbose_name_plural = 'SBE Games'

    game_teams = models.ManyToManyField('sbehost.GameTeam')
    game_name = models.CharField('Game Name', max_length=250)
    game_mode = models.SmallIntegerField('Game Mode', default=0)
    game_paused = models.BooleanField('Game Pause', default=False)
    game_start = models.DateTimeField('Game Start', auto_now_add=True)
    game_finish = models.DateTimeField('Game Finish', blank=True, null=True)
    game_options_cool = models.SmallIntegerField('Game Cool Down', default=300)
    game_options_flag_percent = models.SmallIntegerField('Game Flag Percentage', default=60)
    game_options_ticket_percent = models.SmallIntegerField('Game Ticket Percentage', default=65)
    game_monitors = models.ManyToManyField('sbegame.MonitorServer', through='sbehost.GameMonitor')
    game_host_default_ping_ratio = models.SmallIntegerField('Game Host Pinback Percent', default=50)
    game_options_ticket_wait = models.SmallIntegerField('Game Ticket First Hold Time (Sec)', default=180)
    game_offensive = models.ManyToManyField('sbegame.Player', through='sbehost.GamePlayer',
                                            through_fields=('player_game', 'player'))

    def __str__(self):
        return '%s Game %s (%s-%s) %d Teams' % (('[Running]' if not self.game_paused else '[Paused]'),
                                               self.game_name, self.game_start.strftime('%m/%d/%y %H:%M'),
                                               (self.game_finish.strftime('%m/%d/%y %H:%M')
                                                if self.game_finish else 'Present'), self.game_teams.all().count())


class GameDNS(models.Model):
    __desc__ = """
        SBE Game DNS

        SBE Game DNS is basically a placeholder for a Team's DNS server(s).
    """

    class Meta:
        verbose_name = 'SBE DNS Server'
        verbose_name_plural = 'SBE DNS Servers'

    dns_address = models.CharField('DNS Server Address', max_length=140)

    def __str__(self):
        return 'DNS %s' % self.dns_address


class GameTeam(models.Model):
    BASIC_TEAM_NAMES = [
        'ALPHA',
        'BETA',
        'CHARLIE',
        'DELTA',
        'ECHO',
        'ZETA',
        'EPSILON',
    ]

    __desc__ = """
        SBE Game Team

        The Game Team object is a reference to the players on a team and the data that keeps together the game
        during play, specified by the team.
    """
    __historical__ = True

    static_name = None
    static_color = None

    class Meta:
        verbose_name = 'SBE Game Team'
        verbose_name_plural = 'SBE Game Team'

    # game = models.ForeignKey(Game) # Accessible via (self.game_set.all())
    team_dns = models.ManyToManyField('sbehost.GameDNS')
    team_tickets = models.ManyToManyField('sbehost.GameTicket')
    team = models.ForeignKey('sbegame.Team', blank=True, null=True)  # Reference to existing team, null if auto
    team_score_flags = models.IntegerField('Team Score (Flags)', default=0)
    team_score_basic = models.IntegerField('Team Score (Uptime)', default=0)
    team_score_beacons = models.IntegerField('Team Score (Beacons)', default=0)
    team_score_tickets = models.IntegerField('Team Score (Tickets)', default=0)
    team_players = models.ManyToManyField('sbegame.Player', through='sbehost.GamePlayer',
                                          through_fields=('player_team', 'player_inst'))

    def __len__(self):
        return self.team_score_basic + self.team_score_beacons + self.team_score_flags + self.team_score_tickets

    def __str__(self):
        return 'GameTeam (%s:%d) %s' % (self.get_team_name(), self.get_team_color(), self.__len__())

    def get_team_name(self):
        # Use this instead of .name
        if self.team:
            return self.team.team_name
        if not self.static_name:
            self.static_name = GameTeam.BASIC_TEAM_NAMES[random.randint(0, len(GameTeam.BASIC_TEAM_NAMES)-1)]
        return self.static_name

    def get_team_color(self):
        # Use this instead of .color
        if self.team:
            return self.team.team_color
        if not self.static_color:
            self.static_color = random.randint(0, 66113)
        return self.static_color


class GameHost(models.Model):
    __desc__ = """
        SBE Game Host

        The SBE Game Host is the central structure of the SBE Database.  This struct will host the compromises, flags
        tickets and services that operate with this host.
    """

    class Meta:
        verbose_name = 'SBE Game Host'
        verbose_name_plural = 'SBE Game Hosts'

    ####
    # Additions below by @gambite and also fixes the multigame/team issue that occured during testing
    # Makes lookups for Hosts easier as they are the only object that needs this type of direct lookup method
    # - idf
    game = models.ForeignKey('sbehost.Game')
    game_team = models.ForeignKey('sbehost.GameTeam')
    host_server = models.ForeignKey('sbegame.HostServer')
    host_fqdn = models.CharField('Host Name', max_length=250)
    host_services = models.ManyToManyField('sbehost.GameService')
    host_status = models.BooleanField('Host Online', default=False)
    host_value = models.SmallIntegerField('Host Value', default=250)
    host_flags = models.ManyToManyField('sbehost.GameFlag', blank=True)
    host_tickets = models.ManyToManyField('sbehost.GameTicket', blank=True)
    host_compromises = models.ManyToManyField('sbehost.GameCompromise', blank=True)
    host_ping_ratio = models.SmallIntegerField('Host Pingback Percentage', default=0)
    host_name = models.CharField('Host VM Name', max_length=250, null=True, blank=True)

    def __str__(self):
        return 'Host %s (%s)' % (self.host_fqdn, '; '.join(['%d' % f.service_port for f in self.host_services.all()]))

    def __bool__(self):
        if self.host_compromises.all().filter(comp_finish=None).count() > 0:
            return True
        return False

    def __nonzero__(self):
        return self.__bool__()

    def get_pinback_percent(self):
        if self.host_ping_ratio > 0:
            return self.host_ping_ratio
        try:
            # Look up the stack!
            return self.game.game_host_default_ping_ratio
        except (AttributeError, ValueError):
            pass
        return 50


class GameFlag(models.Model):
    FLAG_VALUES = (
        (1, 'FLAG_TAKEN'),
        (2, 'FLAG_ENABLED'),
        (3, 'FLAG_HIDDEN'),
        (4, 'FLAG_PERMA'),
    )

    __desc__ = """
        SBE Game Flag

        The SBE Flag struct holds the information of flags, mainly what the flag value is and if the flag has been
        taken.
    """

    class Meta:
        verbose_name = 'SBE Game Flag'
        verbose_name_plural = 'SBE Game Flags'

    game = models.ForeignKey(Game)
    game_team = models.ForeignKey(GameTeam)
    flag_name = models.CharField('Flag Name', max_length=250)
    flag_answer = models.CharField('Flag Answer', max_length=500)
    # ^
    # Should Flag Answer just be randomized and that a hidden flag hint would be
    # assigned to this instead? this would prevent not enabled flags from being in
    # the game and would change the flag 'path' meaning turning in flag A would not
    # always give the same answer, if right and would point to different enabled flags.
    # if so, the flag_answer value would be changed to flag_desc and have a description of
    # where to find the flag, like 'root of mail server', etc. -idf
    #
    flag_value = models.SmallIntegerField('Flag Value', default=100)
    flag_option = models.SmallIntegerField('Flag Options', choices=FLAG_VALUES, default=2)
    flag_owner = models.ForeignKey('sbegame.Player', null=True, blank=True, related_name='flag_owner')
    flag_stealer = models.ForeignKey('sbegame.Player', null=True, blank=True, related_name='flag_stealer')

    def __str__(self):
        return 'Flag %s (%d)' % (self.flag_name, self.flag_value)

    def __bool__(self):
        return self.flag_option != 1 and self.flag_online

    def __nonzero__(self):
        return self.__bool__()


class GamePlayer(models.Model):
    __desc__ = """
        SBE Game Player

        This is a Djando through field for Many to Many with player to store additional data, such as score.
    """

    class Meta:
        verbose_name = 'SBE Game Player'
        verbose_name_plural = 'SBE Game Players'

    player = models.ForeignKey('sbegame.Player')
    player_score = models.IntegerField('Player Current Score', default=0)
    player_game = models.ForeignKey('sbehost.Game', null=True, blank=True)      # Only Red Players
    player_team = models.ForeignKey('sbehost.GameTeam', null=True, blank=True)  # Only Blue Players

    def __str__(self):
        return '%s (Score: %d)' % (self.player.player_name, self.player_score)


class GameTicket(models.Model):
    __desc__ = """
        SBE Game Ticket

        A SBE Game Ticket holds the data for the a ticket generated for teams.
    """

    class Meta:
        verbose_name = 'SBE Ticket'
        verbose_name_plural = 'SBE Tickets'

    game_team = models.ForeignKey(GameTeam)
    ticket_name = models.CharField('Ticket Name', max_length=250)
    ticket_value = models.SmallIntegerField('Ticket Value', default=500)
    ticket_expired = models.BooleanField('Ticket Expired', default=False)
    ticket_content = models.CharField('Ticket Body Content', max_length=1000)
    ticket_expires = models.DateTimeField('Ticket Expires', blank=True, null=True)
    ticket_started = models.DateTimeField('Ticket Assigned', blank=True, null=True)
    ticket_completed = models.DateTimeField('Ticket Completed', blank=True, null=True)

    def __len__(self):
        if not self.ticket_started:
            return 0
        if self.ticket_completed:
            return (self.ticket_completed - self.ticket_started).seconds
        if self.ticket_expires:
            return (self.ticket_expires - self.ticket_started).seconds

        tzapp = tz.tzoffset('UTC', 0)
        return (datetime.now(tzapp) - self.ticket_started).seconds

    def __str__(self):
        return 'Ticket %s (%d) %d sec' % (self.ticket_name, self.ticket_value, self.__len__())

    def __bool__(self):
        return self.ticket_completed or self.ticket_expired

    def __nonzero__(self):
        return self.__bool__()


class GameMonitor(models.Model):
    __desc__ = """
        SBE Game Monitor

        This is a Django through object to store additional data for a Many to Many relationship
    """

    class Meta:
        verbose_name = 'SBE Game Monitor'
        verbose_name_plural = 'SBE Game Monitors'

    monitor_game = models.ForeignKey('sbehost.Game')
    monitor_inst = models.ForeignKey('sbegame.MonitorServer')
    monitor_hosts = models.ManyToManyField('sbehost.GameHost')

    def __str__(self):
        return '%s (%s Hosts)' % (self.monitor_inst.__str__(), self.monitor_hosts.all().count())


class GameService(models.Model):
    SERVICE_STATUS = {
        'UP': 0,        # Green
        'DOWN': 1,      # Red
        'ERROR': 2,     # Yellow
        'UNKNOWN': 4,   # ?? (Hot pink lol)
    }

    __desc__ = """
        SBE Game Service

        The SBE Service contains the port/protocol status and configuration for services for each host.
    """

    class Meta:
        verbose_name = 'SBE Service'
        verbose_name_plural = 'SBE Services'

    #  game_host = models.ForeignKey(GameHost) # Accessible via (self.gamehost_set.all())
    service_port = models.SmallIntegerField('Service Port')
    service_name = models.CharField('Service Name', max_length=128)
    service_value = models.SmallIntegerField('Service Value', default=50)
    service_status = models.SmallIntegerField('Service Status', default=0)
    service_bonus = models.BooleanField('Service is Bonus', default=False)
    service_content = models.ForeignKey('sbehost.GameContent', null=True, blank=True)
    service_protocol = models.CharField('Service Protocol', max_length=4, default='tcp')

    def __str__(self):
        ret_host = self.gamehost_set.first()
        return 'SVC %s (%d/%s) %s [%s]' % (self.service_name, self.service_port, self.service_protocol,
                                           self.service_value, ret_host.host_fqdn if ret_host else 'Unassigned')

    def __bool__(self):
        return self.service_status == 0

    def __nonzero__(self):
        return self.__bool__()

    def get_text_status(self):
        for k, v in GameService.SERVICE_STATUS.items():
            if self.service_status == v:
                return k
        return 'UP'


class GameContent(models.Model):
    __desc___ = """
        SBE Service Content

        Contains the content for a service (if any). Content is stored in a pickled field and and can be a string
        or even a dict.  Plugins are stored in dicts.  Content type determines if a plugin is used.
    """

    class Meta:
        verbose_name = 'SBE Service Content'
        verbose_name_plural = 'SBE Service Contents'

    # game_service = models.ForeignKey(GameService # Accessible via (self.gameservice_set.all())
    content_data = PickledObjectField()
    content_type = models.CharField('Content Type', max_length=75, default='string')

    def __str__(self):
        return 'Content (%s)' % self.content_type

    def monitor_json(self):
        return '{ "content_type": "%s", "content_data": %s }' % (self.content_type, json.dumps(self.content_data))


class GameCompromise(models.Model):
    __desc__ = """
        SBE Game Host Compromise

        This will be created when a host is compromised.  Will store the compromises as start/end times
        to easier facilitate the timespan that a host is compromised.
    """
    __historical__ = True

    class Meta:
        verbose_name = 'SBE Host Compromise'
        verbose_name_plural = 'SBE Host Compromises'

    # game_host = models.ForeignKey('GameHost') # Accessible via (self.
    comp_player = models.ForeignKey('sbegame.Player')
    comp_start = models.DateTimeField('Compromise Start', auto_now_add=True)
    comp_finish = models.DateTimeField('Compromise End', null=True, blank=True)

    def __len__(self):
        if self.comp_finish:
            return (self.comp_finish - self.comp_start).seconds
        return (timezone.now() - self.comp_start).seconds

    def __str__(self):
        return '%s (%d seconds)' % (self.comp_player.player_name, self.__len__())

    def __bool__(self):
        return self.comp_finish is None

    def __nonzero__(self):
        return self.__bool__()

    def get_compromised_host(self):
        try:
            return self.host_set.all().first()
        except GameHost.DoesNotExist:
            return None
