using Fixture;
public static class VisibleTests
{
    public static int Main()
    {
        AssertRejected(new Actor(false, 8, 11), 0, 3, 401);
        AssertRejected(new Actor(true, 8, 10), 0, 3, 404);
        AssertRejected(new Actor(true, 7, 11), 3, 4, 404);
        AssertRejected(new Actor(true, 7, 11), 0, 3, 404);
        AssertRejected(new Actor(true, 7, 10), 0, 3, 400);
        AssertRejected(new Actor(true, 7, 10), -1, 4, 400);
        AssertRejected(new Actor(true, 7, 10), 3, 3, 409);
        AssertRejected(new Actor(true, 7, 10), 3, 5, 409);
        var order = new Order(7, 10, 2, 4);
        if (OrderEndpoint.Handle(new Actor(true, 7, 10), order, 3, 4) != 200)
            throw new Exception("Owner update should succeed.");
        if (order.Quantity != 3 || order.Revision != 5)
            throw new Exception("Successful update should change quantity and revision.");
        if (OrderEndpoint.Handle(new Actor(true, 7, 10), order, 9, 4) != 409)
            throw new Exception("A stale edit after a successful update should conflict.");
        if (order.Quantity != 3 || order.Revision != 5)
            throw new Exception("A stale edit should preserve the newer state.");
        Console.WriteLine("Visible checks passed.");
        return 0;
    }

    private static void AssertRejected(Actor actor, int quantity, int expectedRevision, int expectedStatus)
    {
        var order = new Order(7, 10, 2, 4);
        var status = OrderEndpoint.Handle(actor, order, quantity, expectedRevision);
        if (status != expectedStatus)
            throw new Exception($"Expected {expectedStatus}, received {status}.");
        if (order.Quantity != 2 || order.Revision != 4)
            throw new Exception("Rejected updates should preserve quantity and revision.");
    }
}
