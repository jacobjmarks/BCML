import { Button, ButtonGroup, Col, Form, Modal, OverlayTrigger, Tooltip, Row } from "react-bootstrap";

import React from "react";

class ProfileModal extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            profiles: [],
            availableCemuAccounts: [],
            currentProfile: { name: "Default" },
            profileName: "",
            cemuAccount: ""
        };
    }

    componentDidUpdate = prevProps => {
        if (prevProps.show != this.props.show) this.refreshProfiles();
    };

    refreshProfiles = async () => {
        const profiles = await pywebview.api.get_profiles();
        const currentProfile = await pywebview.api.get_current_profile();
        const availableCemuAccounts = await pywebview.api.get_cemu_accounts();
        this.setState({
            profiles,
            profileName: "",
            cemuAccount: "",
            currentProfile: { name: currentProfile },
            availableCemuAccounts
        });
    };

    handleChange = e => {
        try {
            e.persist();
        } catch (error) { }

        this.setState({
            [e.target.id]: e.target.type != "checkbox" ? e.target.value : e.target.checked
        });
    };

    render = () => {
        return (
            <Modal
                show={this.props.show}
                style={{ opacity: this.props.busy ? "0" : "1.0" }}
                onHide={this.props.onClose}>
                <Modal.Header closeButton>
                    <Modal.Title>Mod Profiles</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div className="h5">
                        <strong>Current Profile:</strong> {this.state.currentProfile.name}
                    </div>
                    <Form>
                        <Row>
                            <Col>
                                <Form.Group>
                                    <Form.Control
                                        placeholder="Name new profile"
                                        value={this.state.profileName}
                                        onChange={e =>
                                            this.setState({ profileName: e.currentTarget.value })
                                        }
                                    />
                                </Form.Group>
                            </Col>
                        </Row>
                        <Row>
                            <Col className="pr-0">
                                <Form.Group controlId="cemuAccount">
                                    <OverlayTrigger
                                        overlay={
                                            <Tooltip>
                                                lorum ipsum
                                            </Tooltip>
                                        }>
                                        <Form.Control
                                            as="select"
                                            value={this.state.currentProfile.cemu_account || ""}
                                            onChange={this.handleChange}>
                                            <option value={""}>Associate Cemu account</option>
                                            {this.state.availableCemuAccounts.map(account => (
                                                <option value={account.persistentid} key={account.persistentid}>
                                                    {account.miiname_decoded} ({account.persistentid})
                                                </option>
                                            ))}
                                        </Form.Control>
                                    </OverlayTrigger>
                                </Form.Group>
                            </Col>
                            <Col md="auto">
                                <Form.Group>
                                    <Button
                                        variant="primary"
                                        disabled={!this.state.profileName}
                                        onClick={() =>
                                            this.props.onSave({
                                                name: this.state.profileName,
                                                cemuAccount: this.state.cemuAccount,
                                            }, "save")
                                        }>
                                        Save
                                    </Button>
                                </Form.Group>
                            </Col>
                        </Row>
                    </Form>
                    <div className="h5">Available Profiles</div>
                    {this.state.profiles.length > 0 ? (
                        this.state.profiles.map(profile => (
                            <div
                                className="d-flex flex-row align-items-center mb-1"
                                key={profile.path}>
                                <span>{profile.name}</span>
                                {profile.cemu_account && <span> ({profile.cemu_account})</span>}
                                <div className="flex-grow-1"> </div>
                                <ButtonGroup size="xs">
                                    <Button
                                        variant="success"
                                        title="Load Profile"
                                        onClick={() =>
                                            this.props.onLoad(profile, "load")
                                        }>
                                        <i className="material-icons">refresh</i>
                                    </Button>
                                    <Button
                                        variant="danger"
                                        title="Delete Profile"
                                        onClick={() =>
                                            this.props.onDelete(profile, "delete")
                                        }>
                                        <i className="material-icons">delete</i>
                                    </Button>
                                </ButtonGroup>
                            </div>
                        ))
                    ) : (
                        <p>No profiles yet</p>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <div className="flex-grow-1"></div>
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    };
}

export default ProfileModal;
