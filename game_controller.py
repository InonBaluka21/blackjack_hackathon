from deck import Deck
from deck import Card

class BlackjackGame:
    ROUND_ISNT_OVER = 0
    TIE = 1
    CLIENT_LOSE = 2
    CLIENT_WIN = 3

    def __init__(self, num_of_runs=1):
        self.rounds_num = num_of_runs
        self.runs_left = num_of_runs
        self.wins_count = 0
        self.reset_game()

    def _calculate_score(self, cards):
        """
        Calculates score with 'Soft Ace' logic.
        Ace = 11 usually.
        If score > 21, Ace becomes 1.
        """
        score = 0
        ace_count = 0

        for card in cards:
            score += card.value
            if card.rank == 1:  # Ace
                # score += 11
                ace_count += 1
            #elif card.rank > 10:  # Face cards
            #    score += 10
            #else:
            #    score += card.rank

        # If we busted and have Aces, reduce them from 11 to 1 (subtract 10)
        while score > 21 and ace_count > 0:
            score -= 10
            ace_count -= 1

        return score

    def get_player_score(self):
        return self._calculate_score(self.player_cards)

    def get_dealer_score(self):
        return self._calculate_score(self.dealer_cards)

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
            return BlackjackGame.ROUND_ISNT_OVER  # game is not over

        # player busts (loss)
        if self.is_player_busted:
            return BlackjackGame.CLIENT_LOSE

        # dealer busts (win)
        if self.is_dealer_busted:
            self.wins_count += 1
            return BlackjackGame.CLIENT_WIN

        # compare scores
        client_total = self.get_player_score()
        dealer_total = self.get_dealer_score()
        if client_total > dealer_total:
            self.wins_count += 1
            return BlackjackGame.CLIENT_WIN
        elif client_total < dealer_total:
            return BlackjackGame.CLIENT_LOSE
        else:
            return BlackjackGame.TIE
    
    def has_more_runs(self):
        """
        Checks if there are more game runs left.
        :return: True if more runs are left, False otherwise
        :rtype: bool
        """
        return self.runs_left >= 0

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

    def statistics_print(self):
        print(f"Client finished playing {self.rounds_num} rounds, win rate: {self.wins_count/self.rounds_num:.2%}")
