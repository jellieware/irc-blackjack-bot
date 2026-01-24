import irc.bot
import random

# Blackjack Logic (Simplified)
def get_deck():
    return ['2','3','4','5','6','7','8','9','T','J','Q','K','A'] * 4 * 8 # 8 Decks

def calc_hand(hand):
    val = 0
    aces = 0
    for card in hand:
        if card in ['T','J','Q','K']: val += 10
        elif card == 'A': aces += 1; val += 11
        else: val += int(card)
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val

class BlackjackBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.game_active = False
        self.player_hand = []
        self.dealer_hand = []
        self.deck = []

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        msg = e.arguments[0].lower()
        if msg == "!bj" and not self.game_active:
            self.start_game(c)
        elif msg == "!hit" and self.game_active:
            self.hit(c)
        elif msg == "!stand" and self.game_active:
            self.stand(c)

    def start_game(self, c):
        self.deck = get_deck()
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.game_active = True
        c.privmsg(self.channel, f"Dealer shows: {self.dealer_hand[0]}, You have: {self.player_hand} ({calc_hand(self.player_hand)})")

    def hit(self, c):
        self.player_hand.append(self.deck.pop())
        hand_val = calc_hand(self.player_hand)
        if hand_val > 21:
            c.privmsg(self.channel, f"Bust! {self.player_hand} ({hand_val}). You lose.")
            self.game_active = False
        else:
            c.privmsg(self.channel, f"You hit: {self.player_hand} ({hand_val})")

    def stand(self, c):
        d_val = calc_hand(self.dealer_hand)
        while d_val < 17:
            self.dealer_hand.append(self.deck.pop())
            d_val = calc_hand(self.dealer_hand)
        
        p_val = calc_hand(self.player_hand)
        c.privmsg(self.channel, f"Dealer: {self.dealer_hand} ({d_val})")
        if d_val > 21 or p_val > d_val:
            c.privmsg(self.channel, "You win!")
        elif p_val < d_val:
            c.privmsg(self.channel, "Dealer wins.")
        else:
            c.privmsg(self.channel, "Push (Tie).")
        self.game_active = False

if __name__ == "__main__":
    bot = BlackjackBot("#jellie", "BJBot", "irc.freenode.net")
    bot.start()
