class OrderCalculator:
    def calculate(self, prices, discount):
        total = 0

        for price in prices:
            if price > 0:
                total += price

        if discount:
            total *= 0.9

        return total

def classify_score(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    return "C"
