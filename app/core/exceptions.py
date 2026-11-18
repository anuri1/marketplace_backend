class UserAlreadyExitstsError(Exception):
    pass


class CategoryAlreadyExitstsError(Exception):
    pass


class CategoryNotFoundError(Exception):
    pass


class ItemNotFoundError(Exception):
    pass


class NotEnoughItemsError(Exception):
    pass


class OrderNotFoundError(Exception):
    pass


class OrderCantBeCancelledError(Exception):
    pass


class OrderCantBePaidError(Exception):
    pass


class OrderCantBeCompletedError(Exception):
    pass
