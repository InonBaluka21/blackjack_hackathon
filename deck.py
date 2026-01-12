import random

class Card:
    # Suits Mapping
    SUIT_NAMES = {0: "Hearts", 1: "Diamonds", 2: "Clubs", 3: "Spades"}
    SUIT_SIGNS = {0: "♥", 1: "♦", 2: "♣", 3: "♠"}

    # Rank Names (for printing)
    RANK_NAMES = {
        1: "Ace", 11: "Jack", 12: "Queen", 13: "King"
    }

    def __init__(self, rank: int, suit: int):
        self.rank = rank  # 1-13
        self.suit = suit  # 0-3 (H, D, C, S)

    @property
    def value(self):
        """Returns the Blackjack value of the card (e.g., King=10)."""
        if self.rank > 10:
            return 10
        # currently supporting ace as 1, remove the comments to treat it as 11
        if self.rank == 1:
            return 11  # Simplified Ace (Assignment says Ace is 11)
        return self.rank

    def ascii_art(self):
        """Returns a list of strings representing the card visually."""
        # standard Blackjack abbreviations
        rank_str = self.RANK_NAMES.get(self.rank, str(self.rank))[0]

        # suit mapping
        suit_sym = self.SUIT_SIGNS.get(self.suit, "?")

        # Create the art
        # The logic {rank_str:<2} aligns the text to left/right for 10s (2 digits) vs single digits
        return [
            " .------. ",
            f" |{rank_str:<2}    | ",
            f" |  {suit_sym}   | ",
            f" |    {rank_str:>2}| ",
            " '------' "
        ]

    def __str__(self):
        """Returns 'King of Hearts' or '5 of Spades'."""
        rank_name = self.RANK_NAMES.get(self.rank, str(self.rank))
        suit_name = self.SUIT_NAMES.get(self.suit, "Unknown")
        return f"{rank_name} of {suit_name}"

    def __repr__(self):
        return self.__str__()



class Deck:
    def __init__(self):
        self.cards = []
        self.reset()  # Initialize the deck immediately

    def reset(self):
        """Creates a fresh 52-card deck and shuffles it."""
        # Generate 13 ranks (1-13) for each of the 4 suits (0-3)
        self.cards = [Card(r, s) for r in range(1, 14) for s in range(4)]
        self.shuffle()

    def shuffle(self):
        """Randomizes the order of cards."""
        random.shuffle(self.cards)

    def draw(self):
        """Removes and returns the top card from the deck."""
        if not self.cards:
            # if deck is empty, create a new one
            self.reset()
        return self.cards.pop()