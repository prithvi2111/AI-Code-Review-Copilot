class Reviewer:
    def score(self, issues):
        total = 0
        for issue in issues:
            total += issue.get("weight", 1)
        return total
