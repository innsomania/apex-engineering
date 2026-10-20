namespace Fixture;
public static class OrderEndpoint
{
    public static int Handle(Actor actor, Order order, int quantity, int expectedRevision)
        => OrderService.Update(actor, order, quantity, expectedRevision);
}
