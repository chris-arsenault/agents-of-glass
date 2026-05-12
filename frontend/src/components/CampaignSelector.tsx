import { useSessionStore } from "../store/sessionStore";

export function CampaignSelector() {
  const campaigns = useSessionStore((state) => state.campaigns);
  const campaignId = useSessionStore((state) => state.campaignId);
  const isBootstrapping = useSessionStore((state) => state.isBootstrapping);
  const setCampaign = useSessionStore((state) => state.setCampaign);

  return (
    <label className="scorebug__campaign">
      <span>Campaign</span>
      <select
        aria-label="Campaign"
        className="scorebug__campaign-select"
        disabled={isBootstrapping || campaigns.length === 0}
        onChange={(event) => void setCampaign(event.target.value)}
        value={campaignId}
      >
        {campaigns.length === 0 ? (
          <option value="">No campaigns</option>
        ) : (
          campaigns.map((campaign) => (
            <option key={campaign.campaign_id} value={campaign.campaign_id}>
              {campaign.campaign_id}
            </option>
          ))
        )}
      </select>
    </label>
  );
}
