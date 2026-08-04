class ProgressBar:

    @staticmethod
    def update(current, total):

        percent = int((current / total) * 100)

        bar = "#" * (percent // 2)
        bar += "-" * (50 - len(bar))

        print(
            f"\r[{bar}] {percent}% ({current}/{total})",
            end="",
            flush=True,
        )

        if current == total:
            print()
