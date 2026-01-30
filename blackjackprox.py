import irc.bot
import json
import random
import os
from threading import Timer

# --- 1. Game Logic Classes ---

SUITS = ['Hearts', 'Diamonds', 'Spades', 'Clubs']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'Jack': 10, 'Queen': 10, 'King': 10, 'Ace': 11
}

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = CARD_VALUES[rank]

    def __str__(self):
        return f"{self.rank} of {self.suit}"

class Deck:
    def __init__(self, num_decks=8):
        self.cards = []
        for _ in range(num_decks):
            for suit in SUITS:
                for rank in RANKS:
                    self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)

    def deal_card(self):
        if len(self.cards) > 1:
            return self.cards.pop()
        else:
            # Reshuffle if few cards remain
            self.__init__(8)
            return self.cards.pop()

class Hand:
    def __init__(self):
        self.cards = []
        self.value = 0
        self.aces = 0

    def add_card(self, card):
        self.cards.append(card)
        self.value += card.value
        if card.rank == 'Ace':
            self.aces += 1
        self.adjust_for_ace()

    def adjust_for_ace(self):
        while self.value > 21 and self.aces:
            self.value -= 10
            self.aces -= 1
    
    def display(self, show_all_dealer_cards=False):
        if show_all_dealer_cards:
            return ', '.join(str(card) for card in self.cards) + f" (Value: {self.value})"
        else:
            # For player hand
            return ', '.join(str(card) for card in self.cards) + f" (Value: {self.value})"


# --- 2. Data Persistence ---

DATA_FILE = 'user_data.json'

def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- 3. IRC Bot Implementation ---

class BlackjackBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        super().__init__([(server, port, '')], nickname, nickname)
        self.channel = channel
        self.user_data = load_user_data()
        self.game_active = False
        self.players = {} # {'username': {'hand': Hand, 'bet': amount, 'chips': amount}}
        self.dealer_hand = Hand()
        self.deck = Deck()
        self.game_timer = None # Timer for game timeout

    def on_welcome(self, connection, event):
        connection.join(self.channel)
        connection.privmsg(self.channel, "Blackjack bot is online. Type `!startgame [bet]` to play.")

    def on_pubmsg(self, connection, event):
        message = event.arguments[0].lower().strip()
        nickname = event.source.nick

        if message.startswith('!startgame'):
            self.handle_start_game(connection, nickname, message)
        elif message.startswith('!hit'):
            self.handle_hit(connection, nickname)
        elif message.startswith('!stand'):
            self.handle_stand(connection, nickname)
        elif message.startswith('!balance'):
            self.show_balance(connection, nickname)

    def show_balance(self, connection, nickname):
        if nickname not in self.user_data:
            self.user_data[nickname] = {'chips': 10000, 'bet': 0} # Initial chips
            save_user_data(self.user_data)
        balance = self.user_data[nickname]['chips']
        connection.privmsg(self.channel, f"{nickname}, you have {balance} chips.")

    def handle_start_game(self, connection, nickname, message):
        if self.game_active:
            connection.privmsg(self.channel, "A game is already in progress.")
            return

        try:
            bet = int(message.split()[1])
        except (IndexError, ValueError):
            connection.privmsg(self.channel, "Invalid bet amount. Usage: `!startgame [amount]`")
            return
        
        if nickname not in self.user_data:
            self.user_data[nickname] = {'chips': 10000, 'bet': 0}
        
        if self.user_data[nickname]['chips'] < bet:
            connection.privmsg(self.channel, f"{nickname}, you don't have enough chips. Balance: {self.user_data[nickname]['chips']}")
            return

        self.game_active = True
        self.players[nickname] = {'hand': Hand(), 'bet': bet}
        self.user_data[nickname]['chips'] -= bet
        save_user_data(self.user_data)

        # Deal initial cards (8 decks already set)
        self.players[nickname]['hand'].add_card(self.deck.deal_card())
        self.players[nickname]['hand'].add_card(self.deck.deal_card())
        self.dealer_hand.add_card(self.deck.deal_card())
        self.dealer_hand.add_card(self.deck.deal_card())

        # Announce the hands
        player_hand_str = self.players[nickname]['hand'].display()
        dealer_up_card_str = str(self.dealer_hand.cards[0])
        connection.privmsg(self.channel, f"Game started! {nickname}'s hand: {player_hand_str}.")
        connection.privmsg(self.channel, f"Dealer's up card: {dealer_up_card_str}.")

        # Check for immediate blackjack
        if self.players[nickname]['hand'].value == 21:
            self.resolve_game(connection, nickname, player_blackjack=True)
        else:
            connection.privmsg(self.channel, f"{nickname}, do you want to `!hit` or `!stand`?")
            # Set a timeout for the user to play (optional but good for bots)
            self.game_timer = Timer(60.0, self.timeout_game, args=[connection, nickname])
            self.game_timer.start()

    def handle_hit(self, connection, nickname):
        if not self.game_active or nickname not in self.players:
            return connection.privmsg(self.channel, f"{nickname}, you are not in the current game. Use `!startgame` to play.")

        if self.game_timer:
            self.game_timer.cancel()
        
        self.players[nickname]['hand'].add_card(self.deck.deal_card())
        player_hand_str = self.players[nickname]['hand'].display()
        connection.privmsg(self.channel, f"{nickname}'s hand: {player_hand_str}.")

        if self.players[nickname]['hand'].value > 21:
            self.resolve_game(connection, nickname, player_busted=True)
        elif self.players[nickname]['hand'].value == 21:
            # Automatically stand on 21
            self.handle_stand(connection, nickname)
        else:
            connection.privmsg(self.channel, f"{nickname}, `!hit` or `!stand`?")
            self.game_timer = Timer(60.0, self.timeout_game, args=[connection, nickname])
            self.game_timer.start()


    def handle_stand(self, connection, nickname):
        if not self.game_active or nickname not in self.players:
            return connection.privmsg(self.channel, f"{nickname}, you are not in the current game. Use `!startgame` to play.")
        
        if self.game_timer:
            self.game_timer.cancel()

        connection.privmsg(self.channel, f"{nickname} stands. Dealer's turn.")
        self.dealer_turn(connection, nickname)

    def dealer_turn(self, connection, nickname):
        # Dealer must hit until total is 17 or more
        while self.dealer_hand.value < 17:
            self.dealer_hand.add_card(self.deck.deal_card())
            connection.privmsg(self.channel, f"Dealer hits. Dealer's hand: {self.dealer_hand.display(show_all_dealer_cards=True)}")

        # Resolve the game after dealer finishes
        self.resolve_game(connection, nickname)

    def resolve_game(self, connection, nickname, player_busted=False, player_blackjack=False):
        player_hand = self.players[nickname]['hand']
        dealer_hand = self.dealer_hand
        bet = self.players[nickname]['bet']
        result_message = ""

        # Check game outcome
        if player_busted:
            result_message = f"{nickname} busted! Dealer wins. You lose {bet} chips."
            # Chips already deducted when game started
        elif player_blackjack:
            winnings = int(bet * 1.5) # Blackjack pays 3:2
            self.user_data[nickname]['chips'] += bet + winnings # Return bet + winnings
            result_message = f"{nickname} has Blackjack! You win {winnings} chips."
        elif dealer_hand.value > 21:
            self.user_data[nickname]['chips'] += bet * 2 # Win 1:1, return initial bet + winnings
            result_message = f"Dealer busted! {nickname} wins {bet} chips."
        elif player_hand.value > dealer_hand.value:
            self.user_data[nickname]['chips'] += bet * 2
            result_message = f"{nickname} wins! You win {bet} chips."
        elif dealer_hand.value > player_hand.value:
            result_message = f"Dealer wins! {nickname} loses {bet} chips."
            # Chips already deducted
        else:
            self.user_data[nickname]['chips'] += bet # Push, return initial bet
            result_message = f"It's a push (tie). Your bet of {bet} chips is returned."
        
        # Announce final scores and result
        connection.privmsg(self.channel, f"Final hands -> {nickname}: {player_hand.display()} | Dealer: {dealer_hand.display(show_all_dealer_cards=True)}")
        connection.privmsg(self.channel, result_message)
        connection.privmsg(self.channel, f"{nickname}'s new balance is {self.user_data[nickname]['chips']} chips.")

        # Reset game state
        self.reset_game_state()
        save_user_data(self.user_data)

    def timeout_game(self, connection, nickname):
        if self.game_active and nickname in self.players:
            connection.privmsg(self.channel, f"{nickname} timed out. Game forfeited and bet lost.")
            self.reset_game_state()
            save_user_data(self.user_data)
    
    def reset_game_state(self):
        self.game_active = False
        self.players = {}
        self.dealer_hand = Hand()
        # Deck can persist or reshuffle based on house rules, current implementation reshuffles only when empty.
        if self.game_timer:
            self.game_timer.cancel()
            self.game_timer = None


# --- 4. Running the Bot ---

if __name__ == "__main__":
    # Bot settings
    server = "irc.retronode.org" # Example server
    port = 6667
    channel = "#retronode" # Change to your channel name
    nickname = "BjBotPro"

    # Important Note on Gambling Laws:
    # Running games with real money or anything of value can be considered gambling
    # and may be subject to legal regulations depending on your jurisdiction. 
    # This script is for educational and entertainment purposes only.

    bot = BlackjackBot(channel, nickname, server, port)
    bot.start()
