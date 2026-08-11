import json


class PathfinderError(Exception):
    code = "pathfinder_error"
    exit_code = 2

    def as_dict(self):
        return {"error": {"code": self.code, "message": str(self)}}

    def as_json(self):
        return json.dumps(self.as_dict(), sort_keys=True)


class UsageError(PathfinderError):
    code = "usage_error"


class CapabilityError(PathfinderError):
    code = "capability_error"
    exit_code = 3


class StateError(PathfinderError):
    code = "state_error"
    exit_code = 4


class PolicyError(PathfinderError):
    code = "policy_error"
    exit_code = 5
