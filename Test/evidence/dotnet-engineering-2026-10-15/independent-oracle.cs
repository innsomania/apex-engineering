using Fixture;
public static class IndependentProbe
{
    public static int Main()
    {
        int count = 0;
        foreach (bool authenticated in new[] { false, true })
        foreach (int user in new[] { 7, 8 })
        foreach (int tenant in new[] { 10, 20 })
        foreach (int quantity in new[] { -1, 0, 1, 5 })
        foreach (int revision in new[] { 3, 4, 5 })
        {
            var order = new Order(7, 10, 2, 4);
            int expected = !authenticated ? 401 : user != 7 || tenant != 10 ? 404
                : quantity <= 0 ? 400 : revision != 4 ? 409 : 200;
            int actual = OrderEndpoint.Handle(new Actor(authenticated, user, tenant),
                order, quantity, revision);
            if (actual != expected || order.Quantity != (expected == 200 ? quantity : 2)
                || order.Revision != (expected == 200 ? 5 : 4))
                throw new Exception($"Case {count}: status={actual}, expected={expected}, quantity={order.Quantity}, revision={order.Revision}");
            count++;
        }
        var repeated = new Order(7, 10, 2, 4);
        var actor = new Actor(true, 7, 10);
        if (OrderEndpoint.Handle(actor, repeated, 3, 4) != 200
            || OrderEndpoint.Handle(actor, repeated, 9, 4) != 409
            || repeated.Quantity != 3 || repeated.Revision != 5)
            throw new Exception("A repeated stale request changed the order.");
        Console.WriteLine($"{count} independent combinations and one sequential replay passed.");
        return 0;
    }
}
