import irc.bot
import json
import random
import os

class BlackjackBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        super().__init__([(server, port)], nickname, nickname)
        self.channel = channel
        self.db_file = "balances.json"
        self.balances = self.load_balances()
        self.active_games = {}

    def load_balances(self):
        """Loads user balances from JSON."""
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        return {}

    def save_balances(self):
        """Saves current balances to JSON."""
        with open(self.db_file, 'w') as f:
            json.dump(self.balances, f)

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        msg = e.arguments[0].lower().split()
        user = e.source.nick
        
        if not msg: return

        if msg[0] == "!bet":
            self.start_game(c, user, msg)
        elif msg[0] == "!hit":
            self.handle_hit(c, user)
        elif msg[0] == "!stand":
            self.handle_stand(c, user)

    def start_game(self, c, user, msg):
        """Initializes a game and takes a bet."""
        if user in self.active_games:
            c.privmsg(self.channel, f"{user}, finish your current game first!")
            return

        try:
            bet = int(msg[1])
        except (ValueError, IndexError):
            c.privmsg(self.channel, "Usage: !bet <amount>")
            return

        balance = self.balances.get(user, 1000)
        if bet > balance:
            c.privmsg(self.channel, f"Insufficient funds! Your balance: {balance}")
            return

        # Deal initial cards
        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        player_hand = [random.choice(deck), random.choice(deck)]
        dealer_hand = [random.choice(deck), random.choice(deck)]

        self.active_games[user] = {
            "bet": bet,
            "player": player_hand,
            "dealer": dealer_hand,
            "deck": deck
        }

        c.privmsg(self.channel, f"{user} bet {bet}. Hand: {player_hand} (Total: {sum(player_hand)}). Dealer shows: {dealer_hand[0]}. !hit or !stand?")

    def handle_hit(self, c, user):
        """Deals another card to the player."""
        if user not in self.active_games: return
        
        game = self.active_games[user]
        card = random.choice(game["deck"])
        game["player"].append(card)
        total = sum(game["player"])

        if total > 21:
            self.end_game(c, user, "bust")
        else:
            c.privmsg(self.channel, f"{user}: {game['player']} (Total: {total}). !hit or !stand?")

    def handle_stand(self, c, user):
        """Dealer plays until 17 or bust, then compares scores."""
        if user not in self.active_games: return
        
        game = self.active_games[user]
        p_total = sum(game["player"])
        d_total = sum(game["dealer"])

        while d_total < 17:
            game["dealer"].append(random.choice(game["deck"]))
            d_total = sum(game["dealer"])

        if d_total > 21 or p_total > d_total:
            self.end_game(c, user, "win")
        elif p_total == d_total:
            self.end_game(c, user, "push")
        else:
            self.end_game(c, user, "lose")

    def end_game(self, c, user, result):
        game = self.active_games.pop(user)
        bet = game["bet"]
        self.balances.setdefault(user, 1000)

        if result == "win":
            self.balances[user] += bet
            msg = f"Win! You gained {bet}."
        elif result == "lose" or result == "bust":
            self.balances[user] -= bet
            msg = f"{result.capitalize()}! You lost {bet}."
        else:
            msg = "Push! Bet returned."

        self.save_balances()
        c.privmsg(self.channel, f"{user}: {msg} Dealer had {sum(game['dealer'])}. New Balance: {self.balances[user]}")

if __name__ == "__main__":
    bot = BlackjackBot("#bjpro", "BJBot", "irc.freenode.net")
    bot.start()
