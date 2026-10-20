namespace Fixture;
public sealed record Actor(bool Authenticated, int UserId, int TenantId);
public sealed class Order(int ownerId, int tenantId, int quantity, int revision)
{
    public int OwnerId { get; } = ownerId;
    public int TenantId { get; } = tenantId;
    public int Quantity { get; set; } = quantity;
    public int Revision { get; set; } = revision;
}
public static class OrderService
{
    public static int Update(Actor actor, Order order, int quantity, int expectedRevision)
    {
        if (!actor.Authenticated) return 401;
        if (actor.UserId != order.OwnerId) return 404;
        if (quantity <= 0) return 400;
        order.Quantity = quantity;
        order.Revision++;
        return 200;
    }
}
