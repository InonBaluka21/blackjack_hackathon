from deck import Deck
from deck import Card

class BlackjackGame:
    def __init__(self, num_of_runs=1):
        self.runs_left = num_of_runs
        self.reset_game()

    def get_player_score(self):
        return sum(card.value for card in self.player_cards)

    def get_dealer_score(self):
        return sum(card.value for card in self.dealer_cards)

    def player_hit(self):
        """
        Draws a card for the player.
        Player busts if the total exceeds 21.
        :return: The drawn card object
        :rtype: Card
        """
        if self.is_game_over:
            raise Exception("Game Over")
        if self.is_player_busted:
            raise Exception("Player busted")

        card = self.deck.draw()
        self.player_cards.append(card)

        # player busts (Loss)
        if self.get_player_score() > 21:
            self.is_player_busted = True
            self.is_game_over = True

        return card

    def dealer_play(self):
        """
        The dealer draws a card.
        Dealer stops drawing cards when they bust or their total is 17 or higher.
        :return: The drawn card object
        :rtype: Card
        """
        if self.is_game_over:
            raise Exception("Game Over")
        if self.is_dealer_busted:
            raise Exception("Dealer busted")

        card = self.deck.draw()
        self.dealer_cards.append(card)
        sum_cards = self.get_dealer_score()

        # dealer busts (Loss)
        if sum_cards > 21:
            self.is_dealer_busted = True
            self.is_game_over = True
        # dealer stops drawing cards
        elif sum_cards >= 17:
            self.is_game_over = True

        return card

    def decide_game_status(self):
        """
        Decides the status of the game.
        Game statuses: 
            0 - game isn't over
            1 - tie
            2 - player lost
            3 - player won
        :return: The game status
        :rtype: int
        """
        if not self.is_game_over:
            return 0  # game is not over

        # player busts (Loss)
        if self.is_player_busted:
            return 2

        # dealer busts (Loss)
        if self.is_dealer_busted:
            return 3

        # compare scores
        client_total = self.get_player_score()
        dealer_total = self.get_dealer_score()
        if client_total > dealer_total:
            return 3  # player wins
        elif client_total < dealer_total:
            return 2  # player loses
        else:
            return 1  # tie
    
    def has_more_runs(self):
        """
        Checks if there are more game runs left.
        :return: True if more runs are left, False otherwise
        :rtype: bool
        """
        return self.runs_left > 0

    def reset_game(self):
        """
        Resets the game to start a new round.
        """
        self.deck = Deck()
        self.player_cards = [self.deck.draw(), self.deck.draw()]    # give 2 cards for the client
        self.dealer_cards = [self.deck.draw(), self.deck.draw()]    # give 2 cards for the dealer
        self.is_player_busted = False
        self.is_dealer_busted = False
        self.is_game_over = False
        self.runs_left -= 1
